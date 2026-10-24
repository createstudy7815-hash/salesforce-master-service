import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def ensure_hmac_enabled_for_tests():
    from app.core.config import settings
    orig = settings.HMAC_ENABLED
    settings.HMAC_ENABLED = True
    yield
    settings.HMAC_ENABLED = orig


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_hmac_headers(
    method: str,
    path: str,
    body: bytes = b"",
    client_id: str = "coordinator",
    secret: str = "coordinator-secret-key-sf-master"
) -> dict:
    import time
    import uuid
    from app.core.hmac_auth import generate_hmac_signature

    ts = str(int(time.time()))
    nonce = str(uuid.uuid4())
    sig = generate_hmac_signature(
        method=method,
        path=path,
        timestamp=ts,
        nonce=nonce,
        body=body,
        secret_key=secret
    )
    return {
        "X-SF-Signature": sig,
        "X-SF-Timestamp": ts,
        "X-SF-Client-ID": client_id,
        "X-SF-Nonce": nonce
    }
