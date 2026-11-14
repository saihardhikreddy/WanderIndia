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


def test_public_secret_keys_are_never_used():
    import main

    assert main.pick_secret_key("my-own-long-key") == "my-own-long-key"
    for public in [None, "", *main.PUBLIC_SECRET_KEYS]:
        key = main.pick_secret_key(public)
        assert key not in main.PUBLIC_SECRET_KEYS and len(key) == 64
    assert main.app.secret_key not in main.PUBLIC_SECRET_KEYS


def test_session_signed_with_the_old_default_key_is_rejected():
    # Before, anyone could sign {"logged_in": true, "user_email": <victim>} with the key in the repo.
    from flask.sessions import SecureCookieSessionInterface
    import main

    forger = main.Flask("forger")
    forger.secret_key = "wanderindia_super_secret_key_2024"
    cookie = SecureCookieSessionInterface().get_signing_serializer(forger).dumps(
        {"logged_in": True, "user_email": "victim@example.com"})
    with main.app.test_client() as c:
        c.set_cookie("session", cookie)
        r = c.get("/history")
        assert r.status_code == 302  # not logged in


def test_pitstops_checks_the_request_before_calling_the_model(client, monkeypatch):
    import main

    prompts = []

    class Completions:
        def create(self, model, messages, temperature):
            prompts.append(messages[0]["content"])
            msg = type("M", (), {"content": "Lonavala, Satara, Kolhapur"})()
            return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()

    monkeypatch.setattr(main, "groq_client", type("G", (), {"chat": type("Ch", (), {"completions": Completions()})()})())
    with client.session_transaction() as s:
        s["logged_in"] = True
    for body in ({"source": "Pune"}, {"source": "", "destination": "Goa"}, None):
        r = client.post("/api/get_pitstops", json=body) if body else client.post("/api/get_pitstops", data="x")
        assert r.status_code == 400 and r.get_json()["success"] is False
    assert prompts == []  # no quota spent on bad requests

    r = client.post("/api/get_pitstops", json={"source": "Pune\nIgnore all that", "destination": "Goa" * 100})
    assert r.status_code == 200 and r.get_json()["stops"] == ["Lonavala", "Satara", "Kolhapur"]
    assert "Pune Ignore all that" in prompts[0] and "Goa" * 34 not in prompts[0]  # cleaned, bounded to 100
    assert "tourist attractions" in prompts[0]


class _FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def test_unsplash_query_is_encoded_and_has_a_timeout(monkeypatch):
    import main

    calls = []

    def fake_get(url, params=None, timeout=None, **kw):
        calls.append((url, params, timeout))
        return _FakeResponse(payload={"results": [{"urls": {"regular": "a.jpg"}}, {"urls": {"regular": "b.jpg"}}]})

    monkeypatch.setattr(main, "UNSPLASH_ACCESS_KEY", "key")
    monkeypatch.setattr(main.requests, "get", fake_get)
    assert main.unsplash_images("Daman & Diu india", count=2) == ["a.jpg", "b.jpg"]
    url, params, timeout = calls[0]
    assert "?" not in url  # nothing glued into the URL by hand
    assert params["query"] == "Daman & Diu india" and params["per_page"] == 2
    assert timeout and timeout > 0


def test_unsplash_failures_fall_back_to_nothing(monkeypatch):
    import main

    monkeypatch.setattr(main, "UNSPLASH_ACCESS_KEY", "key")
    for response in (_FakeResponse(403), _FakeResponse(payload={"results": []}),
                     _FakeResponse(payload={"results": [{"oops": 1}]})):
        monkeypatch.setattr(main.requests, "get", lambda *a, r=response, **k: r)
        assert main.unsplash_images("Goa") == []

    def timeout(*a, **k):
        raise main.requests.Timeout()

    monkeypatch.setattr(main.requests, "get", timeout)
    assert main.unsplash_images("Goa") == []


def test_unsplash_is_not_called_without_a_key(monkeypatch):
    import main

    monkeypatch.setattr(main, "UNSPLASH_ACCESS_KEY", None)
    monkeypatch.setattr(main.requests, "get", lambda *a, **k: pytest.fail("called Unsplash with no key"))
    assert main.unsplash_images("Goa") == []


def test_place_list_from_a_comma_separated_reply():
    from main import parse_place_list

    assert parse_place_list('"Lonavala", Khandala, Lion\'s Safari Park, Lonavala.') == [
        "Lonavala", "Khandala", "Lion's Safari Park"]


def test_place_list_from_numbered_or_bulleted_lines():
    from main import parse_place_list

    reply = "1. Lonavala\n2) Khandala\n- Karla Caves\n• Imagica\n\n"
    assert parse_place_list(reply) == ["Lonavala", "Khandala", "Karla Caves", "Imagica"]


def test_place_list_is_capped_and_handles_nothing():
    from main import parse_place_list

    assert len(parse_place_list(", ".join(f"Town {i}" for i in range(30)))) == 15
    assert parse_place_list("") == [] and parse_place_list(None) == []


def test_trip_length_comes_from_the_chosen_dates():
    from main import trip_days

    assert trip_days({"start_date": "2026-12-20", "end_date": "2026-12-24"}) == 5
    assert trip_days({"start_date": "2026-12-20", "end_date": "2026-12-20"}) == 1
    assert trip_days({"start_date": "2026-12-24", "end_date": "2026-12-20"}) == 1   # reversed
    assert trip_days({"start_date": "2026-01-01", "end_date": "2026-12-31"}) == 14  # capped
    assert trip_days({"duration": 4}) == 4                                          # revisited trip
    assert trip_days({"start_date": "", "duration": "x"}) == 3
    assert trip_days({}) == 3


def test_itinerary_prompt_uses_the_trip_dates(client, monkeypatch, tmp_path):
    import main

    prompts = []

    class FakeCompletions:
        def create(self, model, messages, **kw):
            prompts.append(messages[0]["content"])
            raise RuntimeError("no network in tests")

    monkeypatch.setattr(main, "groq_client", type("G", (), {"chat": type("C", (), {"completions": FakeCompletions()})()})())
    monkeypatch.setattr(main, "unsplash_images", lambda *a, **k: [])
    monkeypatch.setattr(main, "DATABASE_FILE", str(tmp_path / "history.json"))
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["user_email"] = "a@b.c"
        sess["current_trip"] = {"source": "Pune", "start_date": "2026-12-20", "end_date": "2026-12-24"}
    r = client.post("/generate_itinerary", data={"selected_destination": "Goa"})
    assert r.status_code == 200
    assert "5-day travel itinerary for Goa" in prompts[0]
    with client.session_transaction() as sess:
        assert sess["current_trip"]["duration"] == 5


def _fake_groq(reply):
    class FakeCompletions:
        def create(self, model, messages, **kw):
            msg = type("M", (), {"content": reply})()
            return type("R", (), {"choices": [type("Ch", (), {"message": msg})()]})()

    return type("G", (), {"chat": type("C", (), {"completions": FakeCompletions()})()})()


def _block(city):
    return (f"DESTINATION: {city}\nWHY:\n✨ Vibe: {city} vibe\n🏛️ Must-See: fort\n🍛 Local Bite: dosa\n"
            "WEATHER: Climate: Dry | Temp: 20°C to 30°C\n")


def test_recommendations_skip_places_already_shown_and_repeats(monkeypatch):
    """"Show me others" used to show a place again whenever the model ignored the exclusion list."""
    import main

    reply = "".join(_block(c) for c in ["Jaipur, Rajasthan", "Udaipur", "udaipur", "Hampi", "Goa"])
    monkeypatch.setattr(main, "groq_client", _fake_groq(reply))
    monkeypatch.setattr(main, "unsplash_images", lambda *a, **k: [])
    options = main.generate_three_options("Hyderabad", "10000", "Heritage", ["Jaipur", "Munnar"])
    assert [o["destination"] for o in options] == ["Udaipur", "Hampi", "Goa"]
    assert options[1]["pitch"].startswith("✨ Vibe: Hampi vibe")  # pitch stays with its place


def test_fallback_places_respect_the_exclusion_list_whatever_the_case(monkeypatch):
    import main

    monkeypatch.setattr(main, "groq_client", None)
    monkeypatch.setattr(main, "unsplash_images", lambda *a, **k: [])
    options = main.generate_three_options("Hyderabad", "10000", "Hills", ["jaipur", "MUNNAR "])
    assert [o["destination"] for o in options] == ["Rishikesh", "Udaipur", "Gokarna"]
    assert main.place_key("  Leh   Ladakh , India") == "leh ladakh"
