import httpx
from app.core.config import settings
from app.models.station import ChargerConnector, ChargingPoint, ChargingStation
from app.models.user import Vehicle, VehicleConnector
from app.services import routing
from tests.helpers import auth, make_listing, make_user


def station(db, name="S", lat=12.97, lon=77.59, conns=(), parking=None, **kw):
    st = ChargingStation(name=name, operator_name="Op", address="a", city="Bengaluru", state="KA", pin_code="1", latitude=lat, longitude=lon,
                         parking_fee=parking, source="manual", **kw)
    db.add(st); db.flush()
    pt = ChargingPoint(station_id=st.id, point_identifier="1"); db.add(pt); db.flush()
    out = []
    for c in conns:
        cc = ChargerConnector(point_id=pt.id, **c); db.add(cc); out.append(cc)
    db.commit()
    return st, out


def vehicle(db, user, connectors=("CCS2",), battery=40.0, ac=7.2, dc=50.0):
    v = Vehicle(user_id=user.id, make="Tata", model="Nexon", year=2024, battery_capacity_kwh=battery, max_ac_charging_kw=ac, max_dc_charging_kw=dc)
    db.add(v); db.flush()
    for c in connectors:
        db.add(VehicleConnector(vehicle_id=v.id, connector_type=c))
    db.commit()
    return v


def test_unknown_price_is_never_filled_in(client, db):
    st, (c,) = station(db, conns=[dict(connector_type="CCS2", current_type="DC", power_kw=60.0)])
    r = client.post("/api/v1/pricing/estimate", json={"target_type": "station", "target_id": st.id, "energy_kwh": 20}).json()
    assert r["is_complete"] is False and r["price_confidence"] == "unknown" and r["total_known"] == 0.0
    assert r["lines"][0] == {"label": "Energy", "amount": None, "basis": "Energy price unavailable", "known": False}
    assert any("Energy charge" in x for x in r["excluded"]) and r["price_verified"] is False
    d = client.get(f"/api/v1/discovery/stations/{st.id}").json()
    assert d["price_summary"] == "Price unavailable" and d["points"][0]["connectors"][0]["pricing_per_kwh"] is None
    assert d["points"][0]["connectors"][0]["price_status"] == "unavailable"
    # price ceilings never match unknown prices
    assert client.get("/api/v1/discovery/stations", params={"max_price_per_kwh": 100}).json() == []


def test_estimate_math_units_and_fee_disclosure(client, db):
    st, (c,) = station(db, parking=20.0, conns=[dict(connector_type="CCS2", current_type="DC", power_kw=50.0, pricing_per_kwh=18.0, session_fee=10.0,
                                                    time_fee_per_min=0.5, idle_fee_per_min=2.0, taxes_included=False, price_source="operator")])
    r = client.post("/api/v1/pricing/estimate", json={"target_type": "station", "target_id": st.id, "energy_kwh": 25}).json()
    lines = {l["label"]: l["amount"] for l in r["lines"]}
    assert lines["Energy"] == 450.0 and lines["Session / connection fee"] == 10.0
    assert lines["Time-based fee"] == 15.0          # 25 kWh / 50 kW = 30 min * 0.5
    assert lines["Parking"] == 10.0                 # 0.5 h * 20
    assert lines["Idle fee"] == 0.0 and r["total_known"] == 485.0
    assert r["is_complete"] is True and any("Taxes" in x for x in r["excluded"])
    assert any("kWh is energy; kW is charging power" in a for a in r["assumptions"]) and any("constant 50 kW" in a for a in r["assumptions"])
    assert r["price_source"] == "operator" and r["price_verified"] is False  # not verified until an admin verifies
    with_idle = client.post("/api/v1/pricing/estimate", json={"target_type": "station", "target_id": st.id, "energy_kwh": 25, "idle_minutes": 10}).json()
    assert with_idle["total_known"] == 505.0


def test_estimate_from_vehicle_battery_and_validation(client, db):
    u = make_user(db, "driver")
    v = vehicle(db, u, battery=40.0)
    st, _ = station(db, conns=[dict(connector_type="CCS2", current_type="DC", power_kw=60.0, pricing_per_kwh=10.0, session_fee=0, time_fee_per_min=0)], parking=0)
    r = client.post("/api/v1/pricing/estimate", headers=auth(u), json={"target_type": "station", "target_id": st.id, "vehicle_id": v.id,
                                                                          "from_soc_percent": 20, "to_soc_percent": 80}).json()
    assert r["energy_kwh"] == 24.0 and r["total_known"] == 240.0 and "losses are not modelled" in r["assumptions"][0]
    assert any("limited by" in a.lower() or "constant 50" in a for a in r["assumptions"])  # vehicle DC limit 50 kW applies to time
    assert client.post("/api/v1/pricing/estimate", json={"target_type": "station", "target_id": st.id}).status_code == 422
    nobatt = vehicle(db, u, battery=None)
    assert client.post("/api/v1/pricing/estimate", headers=auth(u), json={"target_type": "station", "target_id": st.id, "vehicle_id": nobatt.id,
                                                                            "from_soc_percent": 20, "to_soc_percent": 80}).status_code == 400
    other = make_user(db, "driver")
    assert client.post("/api/v1/pricing/estimate", headers=auth(other), json={"target_type": "station", "target_id": st.id, "vehicle_id": v.id, "energy_kwh": 5}).status_code == 404


def test_home_estimate_matches_booking_total(client, db):
    from tests.helpers import book, future_slot
    host, driver = make_user(db, "host"), make_user(db, "driver")
    l = make_listing(db, host, price_per_kwh=10.0)
    est = client.post("/api/v1/pricing/estimate", json={"target_type": "listing", "target_id": l.id, "energy_kwh": 20, "hours": 2}).json()
    b = book(client, driver, l, *future_slot(), kwh=20.0).json()
    assert est["total_known"] == b["total_amount"] == 264.0 and est["price_confidence"] == "confirmed"


def test_compatibility_rules_are_conservative(client, db):
    u = make_user(db, "driver")
    st, _ = station(db, conns=[dict(connector_type="CCS2", current_type="DC", power_kw=120.0), dict(connector_type="CHAdeMO", current_type="DC", power_kw=50.0),
                               dict(connector_type="Type 2", current_type="AC", power_kw=22.0), dict(connector_type="Weird", current_type="DC", power_kw=10.0)])
    ccs_only = vehicle(db, u, connectors=("CCS2",), dc=50.0)
    d = client.get(f"/api/v1/discovery/stations/{st.id}", headers=auth(u), params={"vehicle_id": ccs_only.id}).json()
    assert d["compatibility"]["status"] == "compatible" and d["compatibility"]["effective_power_kw"] == 50.0  # vehicle limit < charger 120
    assert "Limited to 50 kW by your vehicle" in d["compatibility"]["power_note"]

    unknown = vehicle(db, u, connectors=())
    assert client.get(f"/api/v1/discovery/stations/{st.id}", headers=auth(u), params={"vehicle_id": unknown.id}).json()["compatibility"]["status"] == "unconfirmed"

    chademo_only = vehicle(db, u, connectors=("CHAdeMO",))
    only_ccs, _ = station(db, name="CCS only", lat=12.98, conns=[dict(connector_type="CCS2", current_type="DC", power_kw=60.0)])
    c = client.get(f"/api/v1/discovery/stations/{only_ccs.id}", headers=auth(u), params={"vehicle_id": chademo_only.id}).json()["compatibility"]
    assert c["status"] == "incompatible" and "CCS2" in c["reasons"][0] and "CHAdeMO" in c["reasons"][0]
    # CCS2 inlet + Type-2-only AC charger: not assumed compatible
    t2, _ = station(db, name="T2 only", lat=12.99, conns=[dict(connector_type="Type 2", current_type="AC", power_kw=7.0)])
    assert client.get(f"/api/v1/discovery/stations/{t2.id}", headers=auth(u), params={"vehicle_id": ccs_only.id}).json()["compatibility"]["status"] == "unconfirmed"
    # compatible_only filter hides incompatible, keeps unconfirmed/compatible
    res = client.get("/api/v1/discovery/stations", headers=auth(u), params={"vehicle_id": chademo_only.id, "compatible_only": True}).json()
    assert only_ccs.id not in [s["id"] for s in res] and st.id in [s["id"] for s in res]
    # saved vehicle of someone else is not usable; anonymous cannot use vehicle_id
    assert client.get("/api/v1/discovery/stations", params={"vehicle_id": ccs_only.id}).status_code == 401
    assert client.get("/api/v1/discovery/stations", headers=auth(make_user(db, "driver")), params={"vehicle_id": ccs_only.id}).status_code == 404


def test_vehicle_specs_stay_unknown_unless_given(client, db):
    u = make_user(db, "driver")
    r = client.post("/api/v1/users/vehicles", headers=auth(u), json={"make": "Mahindra", "model": "XUV400"})
    assert r.status_code == 201
    v = r.json()
    assert v["battery_capacity_kwh"] is None and v["max_ac_charging_kw"] is None and v["max_dc_charging_kw"] is None and v["connectors"] == []
    upd = client.put(f"/api/v1/users/vehicles/{v['id']}", headers=auth(u), json={"make": "Mahindra", "model": "XUV400", "battery_capacity_kwh": 39.4, "connector_types": ["CCS2", "CCS2", "Type 2"]})
    assert upd.status_code == 200 and sorted(c["connector_type"] for c in upd.json()["connectors"]) == ["CCS2", "Type 2"]


def test_compare_ranks_only_known_prices_as_cheapest(client, db):
    u = make_user(db, "driver")
    host = make_user(db, "host")
    complete, _ = station(db, name="Complete", lat=12.971, parking=0.0, conns=[dict(connector_type="Type 2", current_type="AC", power_kw=22.0, pricing_per_kwh=30.0, session_fee=0.0, time_fee_per_min=0.0)])
    unknown, _ = station(db, name="Unknown price", lat=12.972, conns=[dict(connector_type="Type 2", current_type="AC", power_kw=22.0)])
    partial, _ = station(db, name="Partial", lat=12.973, conns=[dict(connector_type="Type 2", current_type="AC", power_kw=22.0, pricing_per_kwh=1.0)])
    make_listing(db, host, latitude=12.9715, longitude=77.5905, price_per_kwh=25.0, session_fee=0, parking_fee_per_hour=0)
    r = client.get("/api/v1/compare", params={"latitude": 12.97, "longitude": 77.59, "radius_km": 5, "energy_kwh": 10}).json()
    by = {c["name"]: c for c in r["candidates"]}
    assert by["Unknown price"]["estimate"]["total_known"] == 0.0 and by["Unknown price"]["is_lowest_estimated_total"] is False
    assert by["Partial"]["is_lowest_estimated_total"] is False and by["Partial"]["price_label"].startswith("Partial")
    winner = [c for c in r["candidates"] if c["is_lowest_estimated_total"]]
    assert len(winner) == 1 and winner[0]["estimate"]["is_complete"] is True
    assert min(c["estimate"]["total_known"] for c in r["candidates"] if c["estimate"]["is_complete"]) == winner[0]["estimate"]["total_known"]
    assert r["currency"] == "INR" and r["routing"]["road_distance_available"] is False and all(c["road_distance_km"] is None for c in r["candidates"])
    home = next(c for c in r["candidates"] if c["kind"] == "home")
    assert home["is_approximate_location"] is True and home["latitude"] != 12.9715 and home["booking_conditions"]["minimum_hours"] == 1.0
    assert "Secret" not in str(r) and "4455" not in str(r)


def test_navigation_links_and_route_honesty(client, db, monkeypatch):
    st, _ = station(db, lat=12.9716, lon=77.5946, conns=[dict(connector_type="Type 2", current_type="AC", power_kw=7.0)])
    r = client.get("/api/v1/navigation/route", params={"target_type": "station", "target_id": st.id, "origin_lat": 12.9, "origin_lon": 77.5}).json()
    assert r["destination"]["latitude"] == 12.9716 and r["destination"]["is_approximate"] is False
    assert "destination=12.9716%2C77.5946" in r["links"]["google_maps"] and "origin=12.9%2C77.5" in r["links"]["google_maps"]
    assert "daddr=12.9716%2C77.5946" in r["links"]["apple_maps"] and r["in_app_turn_by_turn"] is False
    assert r["route"]["available"] is False and r["route"]["reason"] == "not_configured"  # no invented distance
    txt = client.get("/api/v1/navigation/route", params={"target_type": "station", "target_id": st.id, "origin_text": "MG Road & Trinity"}).json()
    assert "origin=MG%20Road%20%26%20Trinity" in txt["links"]["google_maps"]
    assert client.get("/api/v1/navigation/route", params={"target_type": "station", "target_id": 99999}).status_code == 404
    assert client.get("/api/v1/navigation/route", params={"target_type": "station", "target_id": st.id, "origin_lat": 200, "origin_lon": 0}).status_code == 422

    monkeypatch.setattr(settings, "ROUTING_PROVIDER", "openrouteservice")
    monkeypatch.setattr(settings, "ORS_API_KEY", "ors-key")
    body = {"features": [{"properties": {"summary": {"distance": 12345.0, "duration": 1800.0}}, "geometry": {"coordinates": [[77.5, 12.9], [77.59, 12.97]]}}]}
    monkeypatch.setattr(routing, "_transport", httpx.MockTransport(lambda req: httpx.Response(200, json=body)))
    ok = client.get("/api/v1/navigation/route", params={"target_type": "station", "target_id": st.id, "origin_lat": 12.9, "origin_lon": 77.5}).json()["route"]
    assert ok["available"] is True and ok["distance_km"] == 12.3 and ok["duration_min"] == 30 and ok["geometry"][0] == [12.9, 77.5]
    monkeypatch.setattr(routing, "_transport", httpx.MockTransport(lambda req: httpx.Response(503)))
    bad = client.get("/api/v1/navigation/route", params={"target_type": "station", "target_id": st.id, "origin_lat": 12.9, "origin_lon": 77.5}).json()["route"]
    assert bad["available"] is False and bad["reason"] == "provider_error"
