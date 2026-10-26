import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from app import MODEL, SYSTEM_PROMPT, app


class BackendTests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

    @patch("app.call_ollama")
    def test_health_lists_models(self, call_ollama):
        call_ollama.return_value = {"models": [{"name": "llama3.2:latest"}]}

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "running": True,
            "models": ["llama3.2:latest"],
        })

    @patch("app.call_ollama", side_effect=URLError("connection refused"))
    def test_health_reports_ollama_offline(self, _call_ollama):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertIn("ollama serve", response.get_json()["error"])

    @patch("app.call_ollama")
    def test_chat_sends_prompt_and_returns_reply(self, call_ollama):
        call_ollama.return_value = {"message": {"content": "Hello"}}

        response = self.client.post("/chat", json={"message": "Hi"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"reply": "Hello"})
        call_ollama.assert_called_once_with(
            "/api/chat",
            {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Hi"},
                ],
                "stream": False,
            },
        )
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    def test_chat_rejects_empty_message(self):
        response = self.client.post("/chat", json={"message": " "})

        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.get_json()["error"])

    @patch("app.call_ollama")
    def test_chat_explains_missing_model(self, call_ollama):
        body = json.dumps(
            {"error": f"model '{MODEL}' not found"}
        ).encode("utf-8")
        call_ollama.side_effect = HTTPError(
            "http://localhost:11434/api/chat",
            404,
            "Not Found",
            {},
            io.BytesIO(body),
        )

        response = self.client.post("/chat", json={"message": "Hi"})

        self.assertEqual(response.status_code, 404)
        self.assertIn(f"ollama pull {MODEL}", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
