import sys
from pathlib import Path

# Add WanderIndia root to sys.path so tests run regardless of current directory
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from main import app
from utils import sanitize_input, validate_budget


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


def test_sanitize_input():
    """Verify control character removal and length clamping."""
    assert sanitize_input("  hello\nworld\t  ") == "hello world"
    assert sanitize_input("", default="fallback") == "fallback"
    assert len(sanitize_input("a" * 200, max_len=50)) == 50


def test_validate_budget():
    """Verify budget parsing and clamping."""
    assert validate_budget("₹15,000") == 15000
    assert validate_budget("invalid") == 10000
    assert validate_budget("500", min_val=1000) == 1000
    assert validate_budget("2000000", max_val=1000000) == 1000000
