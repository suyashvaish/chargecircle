from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.security import create_access_token, hash_password
from app.models.community import AuditLog
from app.models.enums import ListingStatus, UserRoleType
from app.models.marketplace import HomeChargerListing
from app.models.user import User, UserRole


def test_admin_metrics_and_moderation_guard(client: TestClient, db: Session):
    admin = User(
        email="admin_test@chargecircle.in",
        hashed_password=hash_password("Pass123!"),
        full_name="Platform Admin",
        is_active=True
    )
    regular = User(
        email="regular_test@chargecircle.in",
        hashed_password=hash_password("Pass123!"),
        full_name="Regular Driver",
        is_active=True
    )
    db.add_all([admin, regular])
    db.flush()
    db.add(UserRole(user_id=admin.id, role_name=UserRoleType.ADMIN.value))
    db.add(UserRole(user_id=regular.id, role_name=UserRoleType.DRIVER.value))
    db.commit()

    admin_token = create_access_token(admin.id)
    regular_token = create_access_token(regular.id)

    # 1. Non-admin forbidden guard
    res_forbid = client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert res_forbid.status_code == 403

    # 2. Admin access success
    res_admin = client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    metrics = res_admin.json()
    assert "total_users" in metrics
    assert "total_bookings" in metrics

    # 3. Moderation action execution
    listing = HomeChargerListing(
        host_id=admin.id,
        title="Listing for Moderation",
        description="Pending review",
        address_street="Test St",
        locality="Test",
        city="Bengaluru",
        state="Karnataka",
        pin_code="560001",
        latitude=12.97,
        longitude=77.60,
        connector_type="Type 2",
        power_kw=7.4,
        price_per_kwh=10.0,
        status=ListingStatus.PENDING_VERIFICATION.value
    )
    db.add(listing)
    db.commit()

    mod_res = client.post(
        "/api/v1/admin/moderation",
        json={
            "target_type": "listing",
            "target_id": listing.id,
            "action": "approved",
            "notes": "Verified earthing compliance"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert mod_res.status_code == 200
    db.refresh(listing)
    assert listing.status == ListingStatus.APPROVED.value

    # Check audit log persisted
    audit = db.query(AuditLog).filter(AuditLog.resource_id == str(listing.id)).first()
    assert audit is not None
    assert "MODERATION" in audit.action
