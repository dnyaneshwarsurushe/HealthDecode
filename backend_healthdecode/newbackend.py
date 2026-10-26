import os
import io
import json
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI
from pypdf import PdfReader

# Load environment variables
load_dotenv()

app = FastAPI(title="ClearLab API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY is missing from your .env file!")

client = OpenAI(api_key=api_key)

SYSTEM_PROMPT = """
You are a patient advocate and medical translator. Your role is educational only.
Do NOT give definitive medical diagnoses or prescribe medications.

Return STRICT JSON matching this exact structure:
{
  "summary": "1-2 sentence high-level overview in reassuring, non-alarmist plain English.",
  "findings": [
    {
      "marker": "Name of biomarker (e.g., Fasting Glucose)",
      "status": "High" | "Low" | "Normal",
      "severity": "Attention Needed" | "Normal" | "Borderline",
      "explanation": "Clear plain-English explanation of what this test measures and why it matters."
    }
  ],
  "doctor_questions": [
    "Specific, high-value question the patient should ask their primary care physician."
  ]
}
"""

def run_llm_analysis(text: str) -> dict:
    """Helper function to call OpenAI model and return JSON output."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this lab report:\n\n{text}"}
        ],
        temperature=0.2
    )
    return json.loads(response.choices[0].message.content)

class ReportRequest(BaseModel):
    report_text: str

# 1. Text endpoint (keeps paste feature functional)
@app.post("/api/translate")
async def translate_report(request: ReportRequest):
    if not request.report_text.strip():
        raise HTTPException(status_code=400, detail="Empty report provided.")
    try:
        return run_llm_analysis(request.report_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 2. PDF Upload endpoint
@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF.")

    try:
        # Read the uploaded file into memory
        contents = await file.read()
        pdf_stream = io.BytesIO(contents)
        reader = PdfReader(pdf_stream)

        extracted_text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                extracted_text += page_text + "\n"

        if not extracted_text.strip():
            raise HTTPException(
                status_code=400, 
                detail="No readable text found in PDF. Scanned image-only PDFs require an OCR tool."
            )

        # Run analysis on extracted text
        return run_llm_analysis(extracted_text)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

# Mount static frontend
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)