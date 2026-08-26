"""Behavior tests for the Gemini GCA bridge (v2 — direct GCA, Cockpit auth)."""
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from gemini_cli_bridge import create_app


class FakeGCA:
    """Patches _gca_call and _access_token so tests never hit the network."""

    def __init__(self):
        self.calls = []

    def gca_call(self, rpc, payload, email):
        self.calls.append((rpc, email))
        if rpc == "fetchAvailableModels":
            return 200, {
                "models": {
                    "gemini-3.6-flash-high": {
                        "displayName": "Gemini 3.6 Flash (High)",
                        "maxTokens": 1048576,
                        "maxOutputTokens": 65536,
                        "supportsThinking": True,
                        "quotaInfo": {"remainingFraction": 1.0},
                    },
                    "claude-sonnet-4-6": {
                        "displayName": "Claude Sonnet 4.6 (Thinking)",
                        "quotaInfo": {"remainingFraction": 0.5},
                    },
                }
            }
        if rpc == "generateContent":
            return 200, {
                "traceId": "trace-1",
                "response": {
                    "candidates": [{
                        "content": {
                            "role": "model",
                            "parts": [
                                {"thoughtSignature": "abc", "text": "hello from gca"},
                            ],
                        },
                        "finishReason": "STOP",
                    }],
                    "usageMetadata": {
                        "promptTokenCount": 10,
                        "candidatesTokenCount": 5,
                        "totalTokenCount": 15,
                    },
                },
            }
        return 404, {"error": "unknown rpc"}


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGCA()
        self.client = TestClient(create_app())
        patcher1 = patch("gemini_cli_bridge._gca_call", side_effect=self.fake.gca_call)
        patcher2 = patch("gemini_cli_bridge._access_token", return_value="fake-at")
        patcher1.start()
        patcher2.start()
        self.addCleanup(patcher1.stop)
        self.addCleanup(patcher2.stop)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_models_live_from_gca(self):
        r = self.client.get("/v1/models")
        self.assertEqual(r.status_code, 200)
        ids = [m["id"] for m in r.json()["data"]]
        self.assertIn("gemini-3.6-flash-high", ids)
        self.assertIn("claude-sonnet-4-6", ids)

    def test_chat_completion_translates(self):
        r = self.client.post("/v1/chat/completions", json={
            "model": "gemini-3.6-flash-high",
            "messages": [{"role": "user", "content": "hi"}],
        })
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["choices"][0]["message"]["content"], "hello from gca")
        self.assertEqual(d["usage"]["prompt_tokens"], 10)
        # verify the GCA payload shape
        rpc, email = self.fake.calls[-1]
        self.assertEqual(rpc, "generateContent")
        self.assertTrue(email)

    def test_chat_unknown_model_still_forwards(self):
        r = self.client.post("/v1/chat/completions", json={
            "model": "whatever", "messages": [{"role": "user", "content": "x"}],
        })
        self.assertEqual(r.status_code, 200)

    def test_account_endpoints(self):
        r = self.client.get("/v1/account")
        self.assertEqual(r.status_code, 200)
        self.assertIn("available", r.json())

    def test_quota_endpoint_shape(self):
        r = self.client.get("/quota")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["logged_in"])
        self.assertIsInstance(d["windows"], list)
        self.assertTrue(any("Gemini" in w["label"] for w in d["windows"]))
        for w in d["windows"][:2]:
            self.assertIn("remaining_percent", w)
            self.assertIn("reset_at", w)
        self.assertTrue(d["details"])


if __name__ == "__main__":
    unittest.main()
