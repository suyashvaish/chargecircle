from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.station import ChargerConnector, ChargingPoint, ChargingStation


def test_public_charger_discovery(client: TestClient, db: Session):
    # Add a public test station
    st = ChargingStation(
        name="Indiranagar Fast Hub",
        operator_name="Tata Power",
        address="100ft Road Indiranagar",
        city="Bengaluru",
        state="Karnataka",
        pin_code="560038",
        latitude=12.9719,
        longitude=77.6412,
        is_sample=True,
        data_source="Test Benchmark"
    )
    db.add(st)
    db.flush()

    pt = ChargingPoint(station_id=st.id, point_identifier="Bay 1")
    db.add(pt)
    db.flush()

    db.add(ChargerConnector(
        point_id=pt.id,
        connector_type="CCS2",
        current_type="DC",
        power_kw=60.0,
        pricing_per_kwh=19.0
    ))
    db.commit()

    # 1. Discover stations by city
    res = client.get("/api/v1/discovery/stations?city=Bengaluru")
    assert res.status_code == 200
    stations = res.json()
    assert len(stations) >= 1
    station = next(s for s in stations if s["id"] == st.id)
    assert station["name"] == "Indiranagar Fast Hub"
    assert station["is_sample"] is True  # Priority 1 requirement: honest sample labeling
    assert "CCS2" in station["connectors_summary"][0]

    # 2. Filter by coordinates with radius (Koramanagala ~ 4km away)
    res_geo = client.get("/api/v1/discovery/stations?latitude=12.9352&longitude=77.6146&radius_km=10.0")
    assert res_geo.status_code == 200
    geo_stations = res_geo.json()
    assert any(s["id"] == st.id for s in geo_stations)

    # 3. Retrieve details
    res_detail = client.get(f"/api/v1/discovery/stations/{st.id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert len(detail["points"]) == 1
    assert detail["points"][0]["connectors"][0]["connector_type"] == "CCS2"
