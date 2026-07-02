import os
import pytest
import mongomock
from unittest.mock import patch

from utils.jwt_auth import create_access_token

TEST_SECRET_KEY = 'test-secret-key-minimum-32-chars-long-for-pytest'
os.environ['FLASK_SECRET_KEY'] = TEST_SECRET_KEY
os.environ['JWT_SECRET'] = TEST_SECRET_KEY


@pytest.fixture(scope='session', autouse=True)
def mock_mongo_client_session():
    with patch('pymongo.MongoClient', mongomock.MongoClient):
        yield


@pytest.fixture(autouse=True)
def mock_db(mock_mongo_client_session):
    from database.databaseConfig import db
    # ensure a clean state before each test
    for collection in db.list_collection_names():
        db[collection].delete_many({})

    yield db


@pytest.fixture
def app(mock_mongo_client_session):
    # app was imported lazily so the mongo patch is already active at import time.
    from app import app as flask_app
    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": TEST_SECRET_KEY,
    })
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def admin_token(app):
    with app.app_context():
        return create_access_token(user_id="mock_admin_id", role="admin")