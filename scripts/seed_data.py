import os
import sys
from datetime import datetime, time, timezone

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models.enums import CurrentType, ListingStatus, OperationalStatus, PointStatus, UserRoleType
from app.models.marketplace import (
    AvailabilitySchedule,
    HomeChargerListing,
    HostVerificationRecord,
    ListingPhoto,
)
from app.models.reliability import ChargerStatusSnapshot
from app.models.station import ChargerConnector, ChargingPoint, ChargingStation
from app.models.user import User, UserProfile, UserRole, Vehicle, VehicleConnector


def seed_database():
    if settings.is_production:
        raise SystemExit("Refusing to seed sample data in production.")
    if settings.ADMIN_PASSWORD == "AdminSecurePassword123!":
        print("[Seed] WARNING: using the default development admin password. Set ADMIN_PASSWORD in your .env.")
    print("[Seed] Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Seed Primary Platform Administrator
        admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if not admin_user:
            print(f"[Seed] Creating platform administrator: {settings.ADMIN_EMAIL}")
            admin_user = User(
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                full_name=settings.ADMIN_NAME,
                phone_number="+91 98765 43210",
                is_active=True,
                is_verified=True
            )
            db.add(admin_user)
            db.flush()
            for r in [UserRoleType.ADMIN.value, UserRoleType.HOST.value, UserRoleType.DRIVER.value]:
                db.add(UserRole(user_id=admin_user.id, role_name=r))
            db.add(UserProfile(user_id=admin_user.id, bio="ChargeCircle Platform Lead Administrator", preferred_city="Bengaluru"))
        else:
            print(f"[Seed] Admin user already exists: {admin_user.email}")

        # 2. Seed Demo Host
        host_user = db.query(User).filter(User.email == "host@chargecircle.in").first()
        if not host_user:
            print("[Seed] Creating demo host user: host@chargecircle.in")
            host_user = User(
                email="host@chargecircle.in",
                hashed_password=hash_password("HostSecurePassword123!"),
                full_name="Rajesh Sharma",
                phone_number="+91 98111 22334",
                is_active=True,
                is_verified=True
            )
            db.add(host_user)
            db.flush()
            db.add(UserRole(user_id=host_user.id, role_name=UserRoleType.HOST.value))
            db.add(UserRole(user_id=host_user.id, role_name=UserRoleType.DRIVER.value))
            db.add(UserProfile(
                user_id=host_user.id,
                bio="EV enthusiast with solar-powered home wallbox in Koramangala.",
                preferred_city="Bengaluru",
                address_line="14th Main, 4th Block, Koramangala, Bengaluru"
            ))

        # 3. Seed Demo Driver
        driver_user = db.query(User).filter(User.email == "driver@chargecircle.in").first()
        if not driver_user:
            print("[Seed] Creating demo driver user: driver@chargecircle.in")
            driver_user = User(
                email="driver@chargecircle.in",
                hashed_password=hash_password("DriverSecurePassword123!"),
                full_name="Pooja Rao",
                phone_number="+91 98222 33445",
                is_active=True,
                is_verified=True
            )
            db.add(driver_user)
            db.flush()
            db.add(UserRole(user_id=driver_user.id, role_name=UserRoleType.DRIVER.value))
            db.add(UserProfile(user_id=driver_user.id, bio="Tech professional driving Tata Nexon EV Max", preferred_city="Bengaluru"))
            
            # Add driver's vehicle
            ev = Vehicle(
                user_id=driver_user.id,
                make="Tata",
                model="Nexon EV Max",
                year=2024,
                trim="Empowered+",
                battery_capacity_kwh=40.5,
                max_ac_charging_kw=7.2,
                max_dc_charging_kw=50.0,
                license_plate="KA 03 MX 4050",
                is_primary=True
            )
            db.add(ev)
            db.flush()
            db.add(VehicleConnector(vehicle_id=ev.id, connector_type="CCS2"))
            db.add(VehicleConnector(vehicle_id=ev.id, connector_type="Type 2"))

        # 4. Seed Curated Public Stations (explicitly marked with is_sample=True)
        if db.query(ChargingStation).count() == 0:
            print("[Seed] Seeding curated public charging stations...")
            stations_data = [
                {
                    "name": "Tata Power EZ Charge - Indiranagar Club",
                    "operator_name": "Tata Power EZ Charge",
                    "address": "100 Feet Rd, HAL 2nd Stage, Indiranagar",
                    "locality": "Indiranagar",
                    "city": "Bengaluru",
                    "state": "Karnataka",
                    "pin_code": "560038",
                    "lat": 12.9719,
                    "lon": 77.6412,
                    "operating_hours": "24/7 Open",
                    "connectors": [("CCS2", "DC", 60.0, 19.5), ("Type 2", "AC", 22.0, 14.0)],
                    "status": OperationalStatus.CONFIRMED_OPERATIONAL.value,
                    "conf": 0.92
                },
                {
                    "name": "Zeon Charging - Nexus Mall Koramangala",
                    "operator_name": "Zeon Charging",
                    "address": "Hosur Rd, Chikku Lakshmaiah Layout, Koramangala",
                    "locality": "Koramangala",
                    "city": "Bengaluru",
                    "state": "Karnataka",
                    "pin_code": "560095",
                    "lat": 12.9352,
                    "lon": 77.6146,
                    "operating_hours": "07:00 AM - 11:00 PM",
                    "connectors": [("CCS2", "DC", 120.0, 22.0), ("CCS2", "DC", 60.0, 20.0)],
                    "status": OperationalStatus.CONFIRMED_OPERATIONAL.value,
                    "conf": 0.88
                },
                {
                    "name": "Jio-bp Pulse - Whitefield Main Road",
                    "operator_name": "Jio-bp Pulse",
                    "address": "Opposite Prestige Ozone, Whitefield Main Rd",
                    "locality": "Whitefield",
                    "city": "Bengaluru",
                    "state": "Karnataka",
                    "pin_code": "560066",
                    "lat": 12.9698,
                    "lon": 77.7499,
                    "operating_hours": "24/7 Open",
                    "connectors": [("CCS2", "DC", 60.0, 18.0), ("Type 2", "AC", 7.4, 13.0)],
                    "status": OperationalStatus.LIKELY_OPERATIONAL.value,
                    "conf": 0.78
                },
                {
                    "name": "Statiq Fast Hub - Electronic City Phase 1",
                    "operator_name": "Statiq",
                    "address": "Velankani Tech Park, Electronics City Phase 1",
                    "locality": "Electronic City",
                    "city": "Bengaluru",
                    "state": "Karnataka",
                    "pin_code": "560100",
                    "lat": 12.8452,
                    "lon": 77.6602,
                    "operating_hours": "24/7 Open",
                    "connectors": [("CCS2", "DC", 50.0, 18.5), ("GB/T", "DC", 15.0, 15.0)],
                    "status": OperationalStatus.REPORTED_UNAVAILABLE.value,
                    "conf": 0.85
                },
                {
                    "name": "ChargeZone HyperCharger - MG Road Metro Station",
                    "operator_name": "ChargeZone",
                    "address": "MG Road, Shivaji Nagar",
                    "locality": "MG Road",
                    "city": "Bengaluru",
                    "state": "Karnataka",
                    "pin_code": "560001",
                    "lat": 12.9756,
                    "lon": 77.6066,
                    "operating_hours": "24/7 Open",
                    "connectors": [("CCS2", "DC", 150.0, 23.5), ("Type 2", "AC", 22.0, 14.5)],
                    "status": OperationalStatus.CONFIRMED_OPERATIONAL.value,
                    "conf": 0.94
                },
                {
                    "name": "Tata Power EZ Charge - Bandra Kurla Complex",
                    "operator_name": "Tata Power EZ Charge",
                    "address": "G Block BKC, Bandra East",
                    "locality": "BKC",
                    "city": "Mumbai",
                    "state": "Maharashtra",
                    "pin_code": "400051",
                    "lat": 19.0662,
                    "lon": 72.8687,
                    "operating_hours": "24/7 Open",
                    "connectors": [("CCS2", "DC", 60.0, 21.0), ("Type 2", "AC", 22.0, 15.0)],
                    "status": OperationalStatus.CONFIRMED_OPERATIONAL.value,
                    "conf": 0.90
                },
                {
                    "name": "Jio-bp Pulse - Cyber City Gurugram",
                    "operator_name": "Jio-bp Pulse",
                    "address": "DLF Phase 2, Sector 24, Cyber City",
                    "locality": "Cyber City",
                    "city": "Gurugram",
                    "state": "Haryana",
                    "pin_code": "122002",
                    "lat": 28.4906,
                    "lon": 77.0898,
                    "operating_hours": "24/7 Open",
                    "connectors": [("CCS2", "DC", 120.0, 22.5), ("Type 2", "AC", 11.0, 14.0)],
                    "status": OperationalStatus.CONFIRMED_OPERATIONAL.value,
                    "conf": 0.91
                }
            ]

            for s_info in stations_data:
                st = ChargingStation(
                    name=s_info["name"],
                    operator_name=s_info["operator_name"],
                    address=s_info["address"],
                    locality=s_info["locality"],
                    city=s_info["city"],
                    state=s_info["state"],
                    pin_code=s_info["pin_code"],
                    latitude=s_info["lat"],
                    longitude=s_info["lon"],
                    operating_hours=s_info["operating_hours"],
                    is_sample=True,  # sample data: illustrative locations and prices, never presented as live
                    source="sample",
                    data_source="Sample dataset (illustrative, not live)",
                    parking_fee=None
                )
                db.add(st)
                db.flush()

                # Add Charging Bay
                pt = ChargingPoint(
                    station_id=st.id,
                    point_identifier="Bay 1",
                    status=PointStatus.AVAILABLE.value
                )
                db.add(pt)
                db.flush()

                for conn_type, cur_type, kw, price in s_info["connectors"]:
                    db.add(ChargerConnector(
                        point_id=pt.id,
                        connector_type=conn_type,
                        current_type=cur_type,
                        power_kw=kw,
                        pricing_per_kwh=price,
                        price_source="sample",  # session/time/idle fees and taxes stay unknown (NULL)
                    ))

                # Add baseline status snapshot
                db.add(ChargerStatusSnapshot(
                    station_id=st.id,
                    operational_status=s_info["status"],
                    confidence_score=s_info["conf"],
                    evidence_summary="Sample dataset baseline (not live data)",
                    total_reports_evaluated=3,
                    positive_weight=2.5 if s_info["status"] != OperationalStatus.REPORTED_UNAVAILABLE.value else 0.2,
                    negative_weight=0.1 if s_info["status"] != OperationalStatus.REPORTED_UNAVAILABLE.value else 3.0,
                    last_reported_at=datetime.now(timezone.utc),
                    calculated_at=datetime.now(timezone.utc)
                ))

        # 5. Seed Home Charging Marketplace Listings
        if db.query(HomeChargerListing).count() == 0 and host_user:
            print("[Seed] Seeding sample home charging facilities...")
            home_listings_data = [
                {
                    "title": "Koramangala Green Wallbox - 7.4kW Type 2",
                    "description": "Covered residential driveway with 7.4kW Schneider Wallbox. Solar powered with dedicated sub-meter and earthing verified by licensed electrician.",
                    "address_street": "House #42, 14th Main Rd, 4th Block",
                    "locality": "Koramangala",
                    "city": "Bengaluru",
                    "pin_code": "560034",
                    "lat": 12.9344,
                    "lon": 77.6285,
                    "power_kw": 7.4,
                    "connector": "Type 2",
                    "price_kwh": 12.5,
                    "session_fee": 15.0,
                    "parking_fee": 10.0,
                    "photo": "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=800&q=80"
                },
                {
                    "title": "Indiranagar Solar-Powered EV Bay - 11kW Fast AC",
                    "description": "Gated independent villa parking with 11kW 3-phase EVSE. Fast AC top-up suitable for MG ZS EV, Ioniq 5, and BYD Atto 3. Clean restroom and Wi-Fi accessible.",
                    "address_street": "Plot 18, 5th Cross, HAL 3rd Stage",
                    "locality": "Indiranagar",
                    "city": "Bengaluru",
                    "pin_code": "560075",
                    "lat": 12.9730,
                    "lon": 77.6520,
                    "power_kw": 11.0,
                    "connector": "Type 2",
                    "price_kwh": 14.0,
                    "session_fee": 20.0,
                    "parking_fee": 15.0,
                    "photo": "https://images.unsplash.com/photo-1558441719-74313f8d6840?auto=format&fit=crop&w=800&q=80"
                },
                {
                    "title": "HSR Layout Safe Overnight 16A EV Socket",
                    "description": "Budget-friendly 3.3kW 16A heavy-duty industrial socket with RCBO safety protection. Ideal for overnight trickle charging of electric 2-wheelers and cars.",
                    "address_street": "122, Sector 1, 27th Main",
                    "locality": "HSR Layout",
                    "city": "Bengaluru",
                    "pin_code": "560102",
                    "lat": 12.9121,
                    "lon": 77.6446,
                    "power_kw": 3.3,
                    "connector": "16A 3-Pin Socket",
                    "price_kwh": 9.5,
                    "session_fee": 10.0,
                    "parking_fee": 5.0,
                    "photo": "https://images.unsplash.com/photo-1563720223185-11003d516935?auto=format&fit=crop&w=800&q=80"
                }
            ]

            for h_info in home_listings_data:
                hl = HomeChargerListing(
                    host_id=host_user.id,
                    title=h_info["title"],
                    description=h_info["description"],
                    address_street=h_info["address_street"],
                    locality=h_info["locality"],
                    city=h_info["city"],
                    state="Karnataka",
                    pin_code=h_info["pin_code"],
                    latitude=h_info["lat"],
                    longitude=h_info["lon"],
                    is_address_hidden_until_booked=True,
                    connector_type=h_info["connector"],
                    power_kw=h_info["power_kw"],
                    price_per_kwh=h_info["price_kwh"],
                    session_fee=h_info["session_fee"],
                    parking_fee_per_hour=h_info["parking_fee"],
                    status=ListingStatus.APPROVED.value,
                    safety_confirmed=True,
                    earthing_verified=True,
                    rcbo_installed=True,
                    parking_access_instructions="Enter through main iron gate, charger is mounted on left pillar beside meter box."
                )
                db.add(hl)
                db.flush()

                db.add(ListingPhoto(
                    listing_id=hl.id,
                    photo_url=h_info["photo"],
                    caption="Charger Bay",
                    is_cover=True
                ))

                for d in range(7):
                    db.add(AvailabilitySchedule(
                        listing_id=hl.id,
                        day_of_week=d,
                        start_time=time(7, 0),
                        end_time=time(23, 0),
                        is_active=True
                    ))

                db.add(HostVerificationRecord(
                    host_id=host_user.id,
                    listing_id=hl.id,
                    document_type="safety_declaration",
                    verification_status="approved",
                    reviewer_notes="Verified by platform admin"
                ))

        db.commit()
        print("[Seed] Database seeding completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"[Seed Error] {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
