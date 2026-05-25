"""Backend tests for Spark dating app - covers auth, discover, swipe, matches, likes-you,
AI features (date ideas, icebreakers, compatibility), subscription/Stripe, and messaging."""
import os
import time
import json
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://spark-dating-118.preview.emergentagent.com").rstrip("/")

# Hardcoded fallback content to detect AI fallback responses
FALLBACK_DATE_TITLES = {"Coffee & Walk", "Sunset Picnic", "Mini Golf", "Cooking Class", "Live Music"}
FALLBACK_ICEBREAKER_FRAGMENTS = [
    "best thing that happened to you this week",
    "If you could travel anywhere tomorrow",
    "Coffee or tea person",
    "bucket list",
]


# ---------- Auth ----------
class TestAuth:
    def test_login_demo1(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/auth/login",
                            json={"email": "demo1@spark.app", "password": "password123"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 0
        assert "user_id" in data
        assert data.get("profile_complete") is True

    def test_login_demo2(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/auth/login",
                            json={"email": "demo2@spark.app", "password": "password123"}, timeout=30)
        assert r.status_code == 200, r.text
        assert "token" in r.json()

    def test_login_invalid(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/auth/login",
                            json={"email": "demo1@spark.app", "password": "wrong"}, timeout=30)
        assert r.status_code == 401


# ---------- Discover/Swipe/Matches/Likes ----------
class TestCoreFlows:
    def test_discover(self, demo1_auth):
        r = requests.get(f"{BASE_URL}/api/discover", headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "profiles" in body
        assert "swipes_remaining" in body
        assert isinstance(body["profiles"], list)

    def test_matches(self, demo1_auth):
        r = requests.get(f"{BASE_URL}/api/matches", headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 200, r.text
        assert "matches" in r.json()
        assert isinstance(r.json()["matches"], list)

    def test_likes_you(self, demo1_auth):
        r = requests.get(f"{BASE_URL}/api/likes-you", headers=demo1_auth["headers"], timeout=30)
        assert r.status_code == 200, r.text
        assert "count" in r.json()


# ---------- AI Features ----------
class TestAI:
    def test_date_ideas_real_ai(self, demo1_auth):
        r = requests.get(f"{BASE_URL}/api/ai/date-ideas", headers=demo1_auth["headers"], timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "date_ideas" in data, f"Expected key date_ideas, got: {data}"
        ideas = data["date_ideas"]
        assert isinstance(ideas, list) and len(ideas) >= 3, f"Expected >=3 ideas, got {len(ideas)}"
        for idea in ideas:
            assert "title" in idea and "description" in idea
        titles = {i.get("title") for i in ideas}
        # Detect fallback: all 5 fallback titles present means fallback was used
        overlap = titles & FALLBACK_DATE_TITLES
        assert overlap != FALLBACK_DATE_TITLES, (
            f"AI returned HARDCODED FALLBACK date ideas: {titles}. "
            "LLM call failed - check backend logs / EMERGENT_LLM_KEY."
        )

    def test_icebreakers_real_ai(self, demo1_auth, match_id):
        r = requests.get(f"{BASE_URL}/api/ai/icebreakers/{match_id}", headers=demo1_auth["headers"], timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "icebreakers" in data, f"Expected key icebreakers, got: {data}"
        ice = data["icebreakers"]
        assert isinstance(ice, list) and len(ice) >= 3
        text_blob = " ".join(ice).lower()
        matches = sum(1 for frag in FALLBACK_ICEBREAKER_FRAGMENTS if frag.lower() in text_blob)
        assert matches < 3, (
            f"AI returned HARDCODED FALLBACK icebreakers (matched {matches}/4 fallback fragments): {ice}"
        )

    def test_compatibility_real_ai(self, demo1_auth, demo2_auth):
        target = demo2_auth["user_id"]
        r = requests.post(f"{BASE_URL}/api/ai/compatibility/{target}",
                          headers=demo1_auth["headers"], timeout=90)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "score" in data
        score = data["score"]
        assert isinstance(score, (int, float)) and 0 <= score <= 100
        assert "insights" in data and isinstance(data["insights"], list) and len(data["insights"]) >= 1
        # Fallback returns ["Both looking for serious relationships"]; if that's the only insight => fallback
        if len(data["insights"]) == 1 and "serious relationships" in data["insights"][0].lower():
            pytest.fail(f"Compatibility AI returned fallback: {data}")

    def test_compatibility_persisted(self, demo1_auth, demo2_auth):
        """Second call should return cached/persisted result."""
        target = demo2_auth["user_id"]
        r1 = requests.post(f"{BASE_URL}/api/ai/compatibility/{target}",
                           headers=demo1_auth["headers"], timeout=60)
        assert r1.status_code == 200
        r2 = requests.post(f"{BASE_URL}/api/ai/compatibility/{target}",
                           headers=demo1_auth["headers"], timeout=60)
        assert r2.status_code == 200
        # Both should have score
        assert r1.json()["score"] == r2.json()["score"], "Score should be persisted/identical on repeated calls"


# ---------- Subscriptions / Stripe ----------
class TestSubscriptions:
    def test_plans(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/subscription/plans", timeout=30)
        assert r.status_code == 200, r.text
        plans = r.json().get("plans", {})
        assert len(plans) == 4, f"Expected 4 plans, got {len(plans)}: {list(plans)}"
        for key in ["premium_monthly", "premium_yearly", "vip_monthly", "vip_yearly"]:
            assert key in plans

    def test_checkout_stripe(self, demo1_auth):
        r = requests.post(
            f"{BASE_URL}/api/subscription/checkout",
            headers=demo1_auth["headers"],
            json={"plan_id": "premium_monthly", "origin_url": "https://example.com"},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "checkout_url" in data, data
        assert "session_id" in data
        assert "stripe.com" in data["checkout_url"], f"Expected stripe.com in URL, got: {data['checkout_url']}"


# ---------- Messaging ----------
class TestMessaging:
    def test_send_message(self, demo1_auth, match_id):
        r = requests.post(
            f"{BASE_URL}/api/messages",
            headers=demo1_auth["headers"],
            json={"match_id": match_id, "content": "TEST_hello from backend test", "message_type": "text"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        msg = r.json()["message"]
        assert msg["content"] == "TEST_hello from backend test"
        assert msg["sender_id"] == demo1_auth["user_id"]
        assert "_id" not in msg

    def test_get_messages(self, demo2_auth, match_id):
        r = requests.get(f"{BASE_URL}/api/messages/{match_id}", headers=demo2_auth["headers"], timeout=30)
        assert r.status_code == 200, r.text
        msgs = r.json()["messages"]
        assert isinstance(msgs, list)
        assert any("TEST_hello" in m.get("content", "") for m in msgs)

    def test_send_voice_message(self, demo1_auth, match_id):
        # tiny fake audio bytes
        files = {"audio": ("test.webm", b"\x1aE\xdf\xa3" + b"\x00" * 100, "audio/webm")}
        r = requests.post(
            f"{BASE_URL}/api/messages/voice",
            headers={"Authorization": demo1_auth["headers"]["Authorization"]},
            params={"match_id": match_id, "duration": 5},
            files=files,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        msg = r.json()["message"]
        assert msg["message_type"] == "voice"
        assert msg["duration"] == 5
        assert msg["content"].startswith("data:audio/")


# ---------- WebSocket ----------
class TestWebSocket:
    def test_ws_connect_and_typing(self, demo1_auth, demo2_auth, match_id):
        import asyncio
        import websockets

        ws_base = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")

        async def run():
            url1 = f"{ws_base}/api/ws/chat/{match_id}?token={demo1_auth['token']}"
            url2 = f"{ws_base}/api/ws/chat/{match_id}?token={demo2_auth['token']}"
            results = {"presence": False, "typing": False, "message_broadcast": False}
            async with websockets.connect(url1) as ws1:
                async with websockets.connect(url2) as ws2:
                    # Drain initial presence events
                    async def drain(ws, store, label):
                        try:
                            while True:
                                raw = await asyncio.wait_for(ws.recv(), timeout=5)
                                msg = json.loads(raw)
                                store.append(msg)
                                if msg.get("type") == "presence":
                                    results["presence"] = True
                                if msg.get("type") == "typing":
                                    results["typing"] = True
                                if msg.get("type") == "message":
                                    results["message_broadcast"] = True
                        except asyncio.TimeoutError:
                            pass

                    msgs1, msgs2 = [], []
                    # Give some time to receive presence event
                    await asyncio.sleep(1)

                    # demo2 sends typing
                    await ws2.send(json.dumps({"type": "typing", "is_typing": True}))
                    await asyncio.sleep(1)

                    # demo1 sends a message via POST API; both should receive WS broadcast
                    requests.post(
                        f"{BASE_URL}/api/messages",
                        headers=demo1_auth["headers"],
                        json={"match_id": match_id, "content": "TEST_ws_broadcast", "message_type": "text"},
                        timeout=15,
                    )
                    await asyncio.sleep(2)

                    # Collect any pending messages on both sockets
                    await asyncio.gather(drain(ws1, msgs1, "ws1"), drain(ws2, msgs2, "ws2"))

            return results, msgs1, msgs2

        results, msgs1, msgs2 = asyncio.run(run())
        assert results["typing"], f"Typing event not received. ws1={msgs1} ws2={msgs2}"
        assert results["message_broadcast"], f"Message broadcast not received via WS. ws1={msgs1} ws2={msgs2}"
        # Presence event should have been received when peer joined
        assert results["presence"], f"Presence event not received. ws1={msgs1} ws2={msgs2}"

    def test_ws_rejects_invalid_token(self, match_id):
        import asyncio
        import websockets

        ws_base = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        url = f"{ws_base}/api/ws/chat/{match_id}?token=invalid_jwt_token"

        async def run():
            try:
                async with websockets.connect(url) as ws:
                    # Should be closed immediately
                    try:
                        await asyncio.wait_for(ws.recv(), timeout=3)
                    except websockets.exceptions.ConnectionClosed:
                        return True
                    except asyncio.TimeoutError:
                        return False
                return True
            except websockets.exceptions.InvalidStatus:
                return True
            except Exception:
                return True

        assert asyncio.run(run()), "WS should reject invalid token"
