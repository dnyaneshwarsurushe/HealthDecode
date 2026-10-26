import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request

# Change MODEL to use a different Ollama model.
MODEL = "llama3.2"
SYSTEM_PROMPT = "You are a helpful assistant."
OLLAMA_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 60

app = Flask(__name__)


def call_ollama(endpoint, payload=None):
    """Send a JSON request to the local Ollama server."""
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    ollama_request = Request(
        f"{OLLAMA_URL}{endpoint}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )

    with urlopen(ollama_request, timeout=OLLAMA_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def ollama_unavailable_response():
    """Return a consistent message when the local Ollama server is offline."""
    return jsonify({"error": "Ollama is not running. Run 'ollama serve'."}), 503


@app.after_request
def add_cors_headers(response):
    # Allow a separate browser-based frontend to call this API.
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.get("/health")
def health():
    """Check Ollama and return the names of models available locally."""
    try:
        result = call_ollama("/api/tags")
    except HTTPError as error:
        return jsonify({"error": f"Ollama returned HTTP {error.code}."}), 502
    except (URLError, TimeoutError):
        return ollama_unavailable_response()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return jsonify({"error": "Ollama returned an invalid response."}), 502

    if not isinstance(result, dict):
        return jsonify({"error": "Ollama returned an invalid response."}), 502

    pulled_models = result.get("models")
    if not isinstance(pulled_models, list):
        return jsonify({"error": "Ollama returned an invalid response."}), 502

    models = [
        model["name"]
        for model in pulled_models
        if isinstance(model, dict) and isinstance(model.get("name"), str)
    ]
    return jsonify({"running": True, "models": models})


@app.post("/chat")
def chat():
    """Send a user's message to the configured local Ollama model."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Send a JSON object with a non-empty 'message'."}), 400

    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "The 'message' field must be a non-empty string."}), 400

    try:
        result = call_ollama(
            "/api/chat",
            {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
                "stream": False,
            },
        )
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        if MODEL.lower() in details.lower() and "not found" in details.lower():
            return (
                jsonify(
                    {"error": f"Model '{MODEL}' not found. Run 'ollama pull {MODEL}'."}
                ),
                404,
            )
        return jsonify({"error": f"Ollama returned HTTP {error.code}."}), 502
    except (URLError, TimeoutError):
        return ollama_unavailable_response()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return jsonify({"error": "Ollama returned an invalid response."}), 502

    if not isinstance(result, dict):
        return jsonify({"error": "Ollama returned an invalid response."}), 502

    message_result = result.get("message")
    reply = message_result.get("content") if isinstance(message_result, dict) else None
    if not isinstance(reply, str):
        return jsonify({"error": "Ollama returned a response without a reply."}), 502

    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)