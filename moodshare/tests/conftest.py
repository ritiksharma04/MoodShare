"""
PYTEST CONFIGURATION & FIXTURES
================================

WHAT IS PYTEST?
---------------
Pytest is a testing framework for Python. It lets you write tests like:

    def test_something():
        assert 1 + 1 == 2

Run tests with: pytest tests/

WHAT ARE FIXTURES?
------------------
Fixtures are reusable setup functions that provide data or resources to tests.
They're marked with @pytest.fixture and can be passed as function arguments.

Example:
    @pytest.fixture
    def user():
        return User(username='test')

    def test_user_has_username(user):  # fixture is automatically passed
        assert user.username == 'test'

WHY USE FIXTURES?
-----------------
1. DRY (Don't Repeat Yourself) - setup code shared across tests
2. Isolation - each test gets a fresh fixture instance
3. Cleanup - fixtures can clean up after themselves

TEST DATABASE:
--------------
We use an in-memory SQLite database for tests:
- Fast (no disk I/O)
- Isolated (each test gets fresh database)
- No conflicts with real database
"""

import pytest
from app import app, db
from app.models import User, Post
from config import Config


class TestConfig(Config):
    """
    TEST CONFIGURATION
    ------------------
    Overrides the production config for testing purposes.

    Key differences:
    - TESTING = True: Enables test mode in Flask
    - SQLALCHEMY_DATABASE_URI = 'sqlite://': Uses in-memory database
    - WTF_CSRF_ENABLED = False: Disables CSRF for easier form testing
    """
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'  # In-memory database
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing


@pytest.fixture
def test_app():
    """
    CREATE TEST APPLICATION
    -----------------------
    This fixture creates a Flask app configured for testing.

    The 'yield' keyword is important:
    - Code before yield = setup
    - Code after yield = teardown (cleanup)

    Usage in tests:
        def test_example(test_app):
            # test_app is the configured Flask application
            pass
    """
    app.config.from_object(TestConfig)

    # Create application context
    with app.app_context():
        # Create all database tables
        db.create_all()

        yield app  # Provide the app to the test

        # Cleanup: remove database session and drop all tables
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(test_app):
    """
    CREATE TEST CLIENT
    ------------------
    The test client simulates a browser making requests to your app.

    Usage:
        def test_home_page(client):
            response = client.get('/')
            assert response.status_code == 200

    Methods available:
    - client.get('/path') - GET request
    - client.post('/path', data={...}) - POST request
    - client.put(), client.delete(), etc.
    """
    return test_app.test_client()


@pytest.fixture
def runner(test_app):
    """
    CREATE CLI TEST RUNNER
    ----------------------
    For testing Flask CLI commands (not used in this app, but good to have).
    """
    return test_app.test_cli_runner()


@pytest.fixture
def sample_user(test_app):
    """
    CREATE SAMPLE USER
    ------------------
    Creates a test user in the database.

    This fixture depends on test_app (which sets up the database).
    Pytest automatically handles the dependency chain.

    Usage:
        def test_user_profile(client, sample_user):
            response = client.get(f'/user/{sample_user.username}')
            assert response.status_code == 200
    """
    user = User(username='testuser', email='test@example.com')
    user.set_password('testpass123')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_user2(test_app):
    """
    CREATE SECOND SAMPLE USER
    -------------------------
    For testing features that require multiple users (following, etc.)
    """
    user = User(username='testuser2', email='test2@example.com')
    user.set_password('testpass123')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_post(test_app, sample_user):
    """
    CREATE SAMPLE POST
    ------------------
    Creates a test post belonging to sample_user.

    Notice: This fixture depends on sample_user, which depends on test_app.
    Pytest handles this dependency chain automatically.
    """
    post = Post(body='This is a test post', author=sample_user)
    db.session.add(post)
    db.session.commit()
    return post


@pytest.fixture
def logged_in_client(client, sample_user):
    """
    CREATE LOGGED-IN CLIENT
    -----------------------
    Returns a test client that has already logged in.

    This is useful for testing routes that require authentication.

    HOW LOGIN WORKS IN TESTS:
    1. POST to /login with credentials
    2. Flask stores session cookie
    3. Subsequent requests include the cookie automatically
    """
    client.post('/login', data={
        'username': sample_user.username,
        'password': 'testpass123'
    }, follow_redirects=True)
    return client
