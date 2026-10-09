import pytest
from main import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_home_page_status(client):
    """Verify that home route renders successfully."""
    response = client.get("/")
    assert response.status_code == 200


def test_dashboard_redirects_unauthenticated(client):
    """Verify that unauthenticated access to dashboard redirects to home."""
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/" in response.headers.get("Location", "")


def test_normal_login_session(client):
    """Verify normal login sets session and redirects to dashboard."""
    response = client.post("/normal-login", data={"email": "tester@example.com"}, follow_redirects=False)
    assert response.status_code == 302
    assert "/dashboard" in response.headers.get("Location", "")
