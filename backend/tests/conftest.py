import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.db.session import Base, get_db
from app.main import app

# Test-process configuration (never read from a developer's .env)
settings.ENVIRONMENT = "test"
settings.EMAIL_SEND_SYNC = True
settings.EMAIL_BACKEND = "disabled"
settings.PAYMENT_MODE = "mock"
settings.AUTO_APPROVE_LISTINGS = True
settings.RAZORPAY_WEBHOOK_SECRET = "whsec_test_only"
settings.USE_LIVE_CHARGER_FEED = False

# Test database
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test_chargecircle.db")  # set to a PostgreSQL URL to run the suite on PostgreSQL
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False} if TEST_DB_URL.startswith("sqlite") else {})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    if test_engine.dialect.name == "postgresql":  # same defence-in-depth constraint as migration 0002
        with test_engine.begin() as conn:
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS btree_gist")
            conn.exec_driver_sql("ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap EXCLUDE USING gist (listing_id WITH =, tstzrange(start_time, end_time) WITH &&) WHERE (status IN ('pending','confirmed','in_progress','awaiting_payment'))")
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./test_chargecircle.db"):
        os.remove("./test_chargecircle.db")


@pytest.fixture
def db():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
