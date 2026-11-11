import httpx
import pytest
from app.core.config import settings
from app.models.station import ChargingStation, ChargingPoint, ChargerConnector
from app.services import provider_sync
from app.services.provider_sync import normalize_poi, sync_area


def poi(i=1001, lat=12.9716, lon=77.5946, title="MG Road Fast Hub", cost="₹18.50/kWh", op="Tata Power", conns=None):
    return {"ID": i, "AddressInfo": {"Title": title, "AddressLine1": "1 MG Road", "Town": "Bengaluru", "StateOrProvince": "Karnataka",
                                      "Postcode": "560001", "Latitude": lat, "Longitude": lon},
            "OperatorInfo": {"Title": op}, "UsageType": {"Title": "Public", "IsMembershipRequired": False},
            "UsageCost": cost, "StatusType": {"Title": "Operational"}, "DateLastVerified": "2026-10-01T10:00:00Z",
            "Connections": conns if conns is not None else [
                {"ConnectionType": {"Title": "CCS (Type 2)", "FormalName": "IEC 62196-3 Configuration FF"}, "PowerKW": 60, "CurrentType": {"Title": "DC"}, "Quantity": 2},
                {"ConnectionType": {"Title": "Type 2 (Socket Only)"}, "PowerKW": 22, "CurrentType": {"Title": "AC (Three-Phase)"}}]}


@pytest.fixture
def feed(monkeypatch):
    monkeypatch.setattr(settings, "USE_LIVE_CHARGER_FEED", True)
    monkeypatch.setattr(settings, "OCM_API_KEY", "test-key")
    calls = {"n": 0, "params": None, "headers": None}
    state = {"handler": lambda req: httpx.Response(200, json=[poi()])}

    def handler(req):
        calls["n"] += 1
        calls["params"], calls["headers"] = dict(req.url.params), dict(req.headers)
        return state["handler"](req)
    monkeypatch.setattr(provider_sync, "_transport", httpx.MockTransport(handler))
    return calls, state


def test_normalize_preserves_only_what_the_provider_says():
    n = normalize_poi(poi())
    assert n["external_id"] == "1001" and n["operator_name"] == "Tata Power" and n["access_type"] == "public"
    assert n["price_per_kwh"] == 18.5 and n["source_url"].endswith("/1001")
    assert [(c["connector_type"], c["current_type"], c["power_kw"]) for c in n["connectors"]] == [("CCS2", "DC", 60.0), ("Type 2", "AC", 22.0)]
    for text in ("Free", "₹10 per hour", "Rs 12", "₹18/kWh + ₹30 parking", ""):
        assert normalize_poi(poi(cost=text))["price_per_kwh"] is None  # ambiguous text never becomes a number
    unknown = normalize_poi(poi(conns=[{"ConnectionType": {"Title": "Exotic Plug 9000"}}]))["connectors"][0]
    assert unknown["power_kw"] is None and unknown["connector_type"] == "Exotic Plug 9000" and unknown["current_type"] == "UNKNOWN"
    assert normalize_poi({"ID": 1}) is None and normalize_poi({"ID": 1, "AddressInfo": {"Latitude": 0, "Longitude": 0}}) is None
    assert normalize_poi("garbage") is None


def test_live_sync_stores_provenance_then_serves_cache(client, db, feed):
    calls, _ = feed
    meta = sync_area(db, 12.97, 77.59, 10)
    assert meta["status"] == "live" and calls["n"] == 1 and calls["params"]["countrycode"] == "IN"
    assert calls["headers"]["x-api-key"] == "test-key" and "test-key" not in str(calls["params"])
    st = db.query(ChargingStation).filter_by(external_provider="open_charge_map", external_id="1001").one()
    assert st.source == "open_charge_map" and st.is_sample is False and st.last_synced_at is not None and st.source_url
    assert st.provider_status == "Operational" and st.parking_fee is None
    conn = db.query(ChargerConnector).join(ChargingPoint).filter(ChargingPoint.station_id == st.id, ChargerConnector.connector_type == "CCS2").one()
    assert conn.pricing_per_kwh == 18.5 and conn.price_source == "provider" and conn.session_fee is None and conn.price_verified is False

    assert sync_area(db, 12.97, 77.59, 10)["status"] == "cached" and calls["n"] == 1  # no repeat call for identical area
    # same area, different decimals -> same cache bucket
    assert sync_area(db, 12.9712, 77.5921, 10)["status"] == "cached" and calls["n"] == 1

    res = client.get("/api/v1/discovery/search", params={"latitude": 12.97, "longitude": 77.59, "radius_km": 5}).json()
    assert res["provider"]["status"] == "cached"
    s = next(x for x in res["stations"] if x["external_id"] == "1001")
    assert s["data_origin"] == "provider" and s["is_sample"] is False and s["price_summary"] == "From ₹18.50/kWh"
    assert s["current_status"] == "Unknown"  # provider status is not live availability


def test_failures_degrade_gracefully_and_back_off(client, db, feed, monkeypatch):
    calls, state = feed
    local = ChargingStation(name="Local Manual Station", operator_name="Local", address="x", city="Bengaluru", state="KA", pin_code="1",
                            latitude=12.97, longitude=77.59, source="manual", data_source="Manually entered")
    db.add(local); db.commit()

    state["handler"] = lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("slow"))
    m = sync_area(db, 12.5, 77.0, 10)
    assert m["status"] == "timeout" and "timed out" in m["message"]
    assert sync_area(db, 12.5, 77.0, 10)["status"] == "unavailable" and calls["n"] == 1  # backoff: not hammered

    state["handler"] = lambda r: httpx.Response(429, headers={"Retry-After": "30"}, json={})
    assert sync_area(db, 11.5, 77.0, 10)["status"] == "rate_limited"
    state["handler"] = lambda r: httpx.Response(200, content=b"<html>oops</html>")
    assert sync_area(db, 10.5, 77.0, 10)["status"] == "malformed"
    state["handler"] = lambda r: httpx.Response(200, json={"not": "a list"})
    assert sync_area(db, 9.5, 77.0, 10)["status"] == "malformed"
    state["handler"] = lambda r: httpx.Response(500)
    assert sync_area(db, 8.5, 77.0, 10)["status"] == "unavailable"

    # Search still works from local data and says so
    state["handler"] = lambda r: httpx.Response(500)
    res = client.get("/api/v1/discovery/search", params={"latitude": 12.97, "longitude": 77.59, "radius_km": 5}).json()
    assert any(s["name"] == "Local Manual Station" for s in res["stations"])
    assert res["provider"]["status"] in ("unavailable", "timeout", "cached") and "local" in res["provider"]["message"].lower() or res["provider"]["status"] == "cached"
    # Old endpoint keeps returning a plain list
    assert isinstance(client.get("/api/v1/discovery/stations", params={"latitude": 12.97, "longitude": 77.59}).json(), list)


def test_malformed_items_skipped_and_dedupe(client, db, feed):
    calls, state = feed
    db.add(ChargingStation(name="MG Road Fast Hub", operator_name="Tata Power", address="1 MG Road", city="Bengaluru", state="KA",
                           pin_code="560001", latitude=12.9716, longitude=77.5946, source="manual", data_source="Manually entered"))
    db.commit()
    state["handler"] = lambda r: httpx.Response(200, json=[poi(), {"ID": 5}, "junk", poi(i=2002, lat=12.99, lon=77.70, title="Far Hub", op="Other")])
    meta = sync_area(db, 12.98, 77.62, 30)
    assert meta["status"] == "live" and meta["counts"]["deduplicated"] == 1 and meta["counts"]["created"] == 1 and meta["counts"]["skipped"] == 2
    assert db.query(ChargingStation).filter_by(external_id="1001").count() == 0
    # a re-sync updates rather than duplicates
    meta2 = provider_sync._upsert(db, normalize_poi(poi(i=2002, lat=12.99, lon=77.70, title="Far Hub Renamed", op="Other")), meta["fetched_at"])
    assert meta2 == "updated" and db.query(ChargingStation).filter_by(external_id="2002").count() == 1


def test_not_configured_disabled_and_radius_cap(db, monkeypatch):
    monkeypatch.setattr(settings, "USE_LIVE_CHARGER_FEED", False)
    assert sync_area(db, 12.9, 77.5, 10)["status"] == "disabled"
    monkeypatch.setattr(settings, "USE_LIVE_CHARGER_FEED", True)
    monkeypatch.setattr(settings, "OCM_API_KEY", None)
    assert sync_area(db, 12.9, 77.5, 10)["status"] == "not_configured"
    monkeypatch.setattr(settings, "OCM_API_KEY", "k")
    seen = {}
    monkeypatch.setattr(provider_sync, "_transport", httpx.MockTransport(lambda r: (seen.update(dict(r.url.params)), httpx.Response(200, json=[]))[1]))
    m = sync_area(db, 12.9, 77.5, 200)
    assert m["radius_limited"] is True and m["radius_km_used"] == 50.0 and float(seen["distance"]) == 50.0
    assert sync_area(db, 95.0, 77.5, 10)["status"] == "invalid_location"


def test_provenance_labels_for_sample_and_manual(client, db):
    db.add_all([ChargingStation(name="Sample One", operator_name="S", address="a", city="Bengaluru", state="KA", pin_code="1", latitude=12.0, longitude=77.0, is_sample=True, source="sample", data_source="Sample dataset"),
                ChargingStation(name="Manual One", operator_name="M", address="a", city="Bengaluru", state="KA", pin_code="1", latitude=12.5, longitude=77.5, source="manual")])
    db.commit()
    data = {s["name"]: s for s in client.get("/api/v1/discovery/stations").json()}
    assert data["Sample One"]["data_origin"] == "sample" and data["Manual One"]["data_origin"] == "manual"
    assert data["Sample One"]["price_summary"] == "Price unavailable" and data["Sample One"]["parking_fee"] is None
