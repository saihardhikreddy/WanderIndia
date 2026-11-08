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


def test_validate_budget_ignores_decimals_and_extra_text():
    """Paise and trailing text must not be glued onto the rupee amount."""
    assert validate_budget("15000.50") == 15000
    assert validate_budget("₹15,000.00") == 15000
    assert validate_budget("Rs. 20,000 for 2 people") == 20000


def test_regenerate_without_previous_recommendations(client, monkeypatch):
    """Regenerating before any 'recommend' request used to raise KeyError (HTTP 500)."""
    import main

    seen = []

    def fake_options(source, budget, vibe, excluded):
        seen.append(list(excluded))
        return [{"destination": "Goa", "cost": "₹10000", "pitch": "beach", "weather": "sunny", "image_url": ""}]

    monkeypatch.setattr(main, "generate_three_options", fake_options)
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["current_trip"] = {"source": "Hyderabad", "budget": "10000", "vibe": "beach"}
    assert client.post("/regenerate").status_code == 200
    assert client.post("/regenerate").status_code == 200
    assert seen == [[], ["Goa"]]  # the second call excludes what the first one showed


def test_damaged_history_file_does_not_break_history(client, monkeypatch, tmp_path):
    import main

    db = tmp_path / "history.json"
    db.write_text("[{\"user_email\": \"a@b.c\", ", encoding="utf-8")  # cut off mid-write
    monkeypatch.setattr(main, "DATABASE_FILE", str(db))
    assert main.load_trips() == []
    client.post("/normal-login", data={"email": "a@b.c"})
    assert client.get("/history").status_code == 200

    main.save_trip({"user_email": "a@b.c", "destination": "Goa"})
    assert main.get_user_trips("a@b.c") == [{"user_email": "a@b.c", "destination": "Goa"}]
    assert not (tmp_path / "history.json.tmp").exists()


def test_direct_plan_prompt_names_the_destination(client, monkeypatch):
    import main

    prompts = []

    class FakeCompletions:
        def create(self, model, messages, **kw):
            prompts.append(messages[0]["content"])
            raise RuntimeError("no network in tests")  # the route falls back to its default pitch

    fake = type("G", (), {"chat": type("C", (), {"completions": FakeCompletions()})()})()
    monkeypatch.setattr(main, "groq_client", fake)
    monkeypatch.setattr(main.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    with client.session_transaction() as sess:
        sess["logged_in"] = True
    r = client.post("/dashboard", data={"action": "direct", "source": "Hyderabad", "destination": "Hampi",
                                       "budget": "12000", "vibe": "Heritage"})
    assert r.status_code == 200
    assert "Hampi" in prompts[0] and "Hyderabad" in prompts[0] and "12000" in prompts[0]


def test_trip_routes_need_a_login(client, monkeypatch, tmp_path):
    import main

    db = tmp_path / "history.json"
    monkeypatch.setattr(main, "DATABASE_FILE", str(db))
    called = []
    monkeypatch.setattr(main, "groq_client", type("G", (), {"chat": property(lambda s: called.append(1))})())
    r = client.post("/generate_itinerary", data={"selected_destination": "Goa"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/")
    assert not db.exists()  # nothing saved to history without an owner
    assert client.post("/revisit_trip", data={"created_at": "x"}).status_code == 302
    r = client.post("/api/get_pitstops", json={"source": "Pune", "destination": "Goa"})
    assert r.status_code == 401 and r.get_json() == {"success": False, "stops": []}
    assert not called
