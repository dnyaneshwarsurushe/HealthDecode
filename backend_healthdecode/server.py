from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.request
import json

app = Flask(__name__)
CORS(app)  # Enable CORS so your frontend can call this API

# --- CONFIGURATION ---
# The Ollama API endpoint
OLLAMA_URL = "http://localhost:11434"
# The model to use (change this to use a different model)
MODEL = "llama3.2"
# The system prompt to define the assistant's personality/behavior
SYSTEM_PROMPT = "You are a helpful and knowledgeable health assistant. Provide clear, concise, and supportive information."
# ---------------------

def call_ollama(endpoint, data):
    """
    Helper function to make requests to the Ollama API using the standard library.
    """
    url = f"{OLLAMA_URL}{endpoint}"
    try:
        # Convert data dictionary to JSON bytes
        json_data = json.dumps(data).encode('utf-8')

        # Create a request object
        req = urllib.request.Request(
            url,
            data=json_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        # Send request and read response
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))

    except urllib.error.URLError as e:
        # Handle cases where Ollama is not running
        if isinstance(e.reason, ConnectionRefusedError) or "refused" in str(e.reason).lower():
            raise RuntimeError("Ollama is not running. Please run 'ollama serve' to start it.")
        raise RuntimeError(f"Network error connecting to Ollama: {e.reason}")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred: {str(e)}")

@app.route('/chat', methods=['POST'])
def chat():
    """
    Endpoint to chat with the local Ollama model.
    Expects JSON: {"message": "..."}
    Returns JSON: {"reply": "..."}
    """
    data = request.get_json()

    if not data or 'message' not in data:
        return jsonify({"error": "Missing 'message' in request body"}), 400

    user_message = data['message']

    # Construct the payload for the /api/chat endpoint
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "stream": False  # Set to False to get a single complete response
    }

    try:
        response_data = call_ollama("/api/chat", payload)
        # Extract the content of the assistant's message
        reply = response_data['message']['content']
        return jsonify({"reply": reply})

    except RuntimeError as e:
        error_msg = str(e)
        # Specifically handle model not found errors
        if "not found" in error_msg.lower() or "404" in error_msg:
            return jsonify({"reply": f"Model {MODEL} not found. Please run 'ollama pull {MODEL}'"}), 404
        return jsonify({"error": error_msg}), 500

@app.route('/health', methods=['GET'])
def health():
    """
    Endpoint to check if Ollama is running and list available models.
    """
    try:
        # Using /api/tags to list pulled models
        url = f"{OLLAMA_URL}/api/tags"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            models = [m['name'] for m in data.get('models', [])]
            return jsonify({
                "status": "healthy",
                "ollama_running": True,
                "models": models
            })
    except Exception:
        return jsonify({
            "status": "unhealthy",
            "ollama_running": False,
            "error": "Could not connect to Ollama. Please run 'ollama serve'."
        }), 503

if __name__ == '__main__':
    # Run the Flask app on localhost:5000
    app.run(host='0.0.0.0', port=5000, debug=True)
