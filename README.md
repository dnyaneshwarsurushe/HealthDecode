# HealthDecode
HealthDecode is a healthcare project that helps people understand their medical reports in simple and easy language. Many people find it difficult to understand medical terms, test results, and abbreviations in their reports. Our project aims to make this information easier to understand by providing understand result .

## Local Flask backend

The backend uses a locally running Ollama server and the `llama3.2` model by default.

1. Install Ollama, then start its local server in a terminal:

   ```sh
   ollama serve
   ```

2. In another terminal, download the model and start the Flask backend:

   ```sh
   ollama pull llama3.2
   cd backend_healthdecode
   python -m pip install -r requirements.txt
   python app.py
   ```

The API runs at `http://localhost:5000`. `POST /chat` accepts a JSON body such as
`{"message": "Explain this result in simple terms."}` and returns a JSON reply.
`GET /health` reports whether Ollama is running and lists its downloaded models.
The model and system prompt can be changed at the top of `backend_healthdecode/app.py`.
