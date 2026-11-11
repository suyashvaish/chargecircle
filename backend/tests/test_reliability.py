from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.security import create_access_token, hash_password
from app.models.enums import UserRoleType
from app.models.station import ChargingStation
from app.models.user import User, UserRole


def test_reliability_reporting_and_scoring(client: TestClient, db: Session):
    # Setup users
    reporter = User(
        email="reporter@chargecircle.in",
        hashed_password=hash_password("Pass123!"),
        full_name="EV Reporter",
        is_active=True
    )
    db.add(reporter)
    db.flush()
    db.add(UserRole(user_id=reporter.id, role_name=UserRoleType.DRIVER.value))

    station = ChargingStation(
        name="Reliability Test Hub",
        operator_name="Zeon",
        address="123 Road",
        city="Bengaluru",
        state="Karnataka",
        pin_code="560001",
        latitude=12.9756,
        longitude=77.6066,
        is_sample=True,
        data_source="Test"
    )
    db.add(station)
    db.commit()

    reporter_token = create_access_token(reporter.id)

    # 1. Level 1: Submit unverified working report
    rep_payload = {
        "station_id": station.id,
        "category": "working_normally",
        "description": "Charged smoothly at 60kW on Gun 1"
    }
    res_rep = client.post(
        "/api/v1/reliability/reports",
        json=rep_payload,
        headers={"Authorization": f"Bearer {reporter_token}"}
    )
    assert res_rep.status_code == 201, res_rep.text
    rep_data = res_rep.json()
    assert rep_data["evidence_level"] == 1
    assert rep_data["is_verified"] is False

    # 2. Check updated reliability status
    res_status = client.get(f"/api/v1/reliability/status/station/{station.id}")
    assert res_status.status_code == 200
    st_data = res_status.json()
    assert "operational" in st_data["operational_status"].lower()
    assert st_data["total_reports_evaluated"] >= 1

    # 3. Duplicate Detection: Same category within 1 hour must fail
    res_dup = client.post(
        "/api/v1/reliability/reports",
        json=rep_payload,
        headers={"Authorization": f"Bearer {reporter_token}"}
    )
    assert res_dup.status_code == 400
    assert "recently submitted" in res_dup.json()["detail"]
