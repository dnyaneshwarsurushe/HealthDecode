# Lab Report Translator — hackathon starter (Flask + optional local Ollama)
#
# What it does:
#   1. Parses pasted lab report text, finds common test markers and values.
#   2. Flags each value as LOW / Normal / HIGH against the range printed in
#      the report itself when present, otherwise a typical adult range.
#   3. Explains each marker in plain language (built-in meanings).
#   4. Drafts questions for the patient's doctor, in English, Hindi, or Marathi.
#   5. Accepts uploaded reports in any format: .txt, .pdf, .docx, or a photo
#      (.png / .jpg) read with OCR. See /upload and the notes below.
#   6. If Ollama is running locally, it also writes a plain-language summary
#      in the chosen language with a strict no-diagnosis prompt. If Ollama is
#      not running, the app still works fully on built-in meanings — so the
#      demo never breaks.
#
# SAFETY RULES (keep these — judges will ask):
#   - This is EDUCATIONAL ONLY. It never diagnoses and never says what
#     treatment anyone needs. It explains ranges and drafts doctor questions.
#   - Demo ONLY with sample/synthetic reports. Never paste a real person's
#     report on stage, and never store reports: everything is processed in
#     memory and forgotten when the request ends.
#   - Nothing leaves the PC: parsing is local, and Ollama runs locally.
#
# Run:  pip install -r requirements.txt  →  python app.py  →  open index-healthdecode.html
# Optional extras: pip install pypdf          (for PDF uploads)
#                  pip install pillow pytesseract + the Tesseract program
#                  (for photo/scan uploads)

import io
import json
import os
import re
import urllib.error
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

from flask import Flask, jsonify, request

app = Flask(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2"

# Typical adult reference ranges. The range printed in the user's own report
# always wins — the parser uses it whenever it finds one in the pasted text.
# Ranges vary by lab, age, and sex; that is exactly why the app never
# diagnoses and always points to the doctor.
MARKERS = [
    {"key": "fasting_glucose", "label": "Fasting Glucose",
     "aliases": [r"fasting glucose", r"fasting blood sugar", r"fbs"],
     "low": 70, "high": 99, "unit": "mg/dL",
     "meaning": "Blood sugar measured after not eating overnight."},
    {"key": "glucose", "label": "Glucose",
     "aliases": [r"glucose", r"blood sugar"],
     "low": 70, "high": 99, "unit": "mg/dL",
     "meaning": "The amount of sugar in the blood at the time of the test."},
    {"key": "hba1c", "label": "HbA1c",
     "aliases": [r"hba1c", r"a1c"],
     "low": 4.0, "high": 5.6, "unit": "%",
     "meaning": "Average blood sugar level over roughly the past 2–3 months."},
    {"key": "hemoglobin", "label": "Hemoglobin",
     "aliases": [r"hemoglobin", r"haemoglobin", r"\bhb\b"],
     "low": 12.0, "high": 15.5, "unit": "g/dL",
     "meaning": "The protein in red blood cells that carries oxygen around the body."},
    {"key": "wbc", "label": "WBC (White Blood Cells)",
     "aliases": [r"\bwbc\b", r"white blood cells", r"leukocytes"],
     "low": 4.0, "high": 11.0, "unit": "x10^9/L",
     "meaning": "White blood cells help the body fight infections."},
    {"key": "rbc", "label": "RBC (Red Blood Cells)",
     "aliases": [r"\brbc\b", r"red blood cells"],
     "low": 4.0, "high": 5.5, "unit": "million/µL",
     "meaning": "Red blood cells carry oxygen from the lungs to the rest of the body."},
    {"key": "platelets", "label": "Platelets",
     "aliases": [r"platelets?", r"thrombocytes"],
     "low": 150, "high": 450, "unit": "x10^9/L",
     "meaning": "Platelets help the blood clot when you get a cut."},
    {"key": "mcv", "label": "MCV",
     "aliases": [r"\bmcv\b", r"mean corpuscular volume"],
     "low": 80, "high": 100, "unit": "fL",
     "meaning": "The average size of your red blood cells."},
    {"key": "mch", "label": "MCH",
     "aliases": [r"\bmch\b", r"mean corpuscular hemoglobin"],
     "low": 27, "high": 33, "unit": "pg",
     "meaning": "The average amount of hemoglobin in each red blood cell."},
    {"key": "ferritin", "label": "Ferritin",
     "aliases": [r"ferritin"],
     "low": 30, "high": 400, "unit": "ng/mL",
     "meaning": "Ferritin shows how much iron your body has stored."},
    {"key": "iron", "label": "Iron (Serum)",
     "aliases": [r"\biron\b"],
     "low": 60, "high": 170, "unit": "µg/dL",
     "meaning": "Iron is needed to make hemoglobin and carry oxygen."},
    {"key": "vitamin_d", "label": "Vitamin D",
     "aliases": [r"vitamin d", r"vit d", r"25-oh vitamin d"],
     "low": 30, "high": 100, "unit": "ng/mL",
     "meaning": "Vitamin D helps the body absorb calcium for bones."},
    {"key": "vitamin_b12", "label": "Vitamin B12",
     "aliases": [r"vitamin b12", r"\bb12\b"],
     "low": 200, "high": 900, "unit": "pg/mL",
     "meaning": "Vitamin B12 helps make red blood cells and keeps nerves healthy."},
    {"key": "alt", "label": "ALT",
     "aliases": [r"\balt\b", r"alanine aminotransferase"],
     "low": 7, "high": 56, "unit": "U/L",
     "meaning": "ALT is an enzyme mostly found in the liver; it is checked as a liver test."},
    {"key": "ast", "label": "AST",
     "aliases": [r"\bast\b", r"aspartate aminotransferase"],
     "low": 10, "high": 40, "unit": "U/L",
     "meaning": "AST is an enzyme found in the liver and other tissues."},
    {"key": "creatinine", "label": "Creatinine",
     "aliases": [r"creatinine"],
     "low": 0.6, "high": 1.2, "unit": "mg/dL",
     "meaning": "Creatinine is a waste product the kidneys normally filter out."},
    {"key": "egfr", "label": "eGFR",
     "aliases": [r"egfr"],
     "low": 60, "high": 120, "unit": "mL/min/1.73",
     "meaning": "eGFR is an estimate of how well the kidneys are filtering."},
    {"key": "total_cholesterol", "label": "Total Cholesterol",
     "aliases": [r"total cholesterol"],
     "low": 125, "high": 200, "unit": "mg/dL",
     "meaning": "The total amount of cholesterol in the blood."},
    {"key": "ldl", "label": "LDL Cholesterol",
     "aliases": [r"\bldl\b", r"ldl cholesterol"],
     "low": 0, "high": 100, "unit": "mg/dL",
     "meaning": "LDL is often called 'bad' cholesterol."},
    {"key": "hdl", "label": "HDL Cholesterol",
     "aliases": [r"\bhdl\b", r"hdl cholesterol"],
     "low": 40, "high": 60, "unit": "mg/dL",
     "meaning": "HDL is often called 'good' cholesterol."},
    {"key": "triglycerides", "label": "Triglycerides",
     "aliases": [r"triglycerides", r"triglyceride"],
     "low": 0, "high": 150, "unit": "mg/dL",
     "meaning": "Triglycerides are a type of fat found in the blood."},
    {"key": "tsh", "label": "TSH",
     "aliases": [r"\btsh\b", r"thyroid stimulating hormone"],
     "low": 0.4, "high": 4.0, "unit": "mIU/L",
     "meaning": "TSH is a hormone that controls how the thyroid gland works."},
]

# Languages for doctor questions and the AI summary.
# Marker meanings stay in English when Ollama is not running; with Ollama,
# the AI summary is written in the chosen language.
SUPPORTED_LANGS = ("en", "hi", "mr")

QUESTION_TEXT = {
    "en": {
        "cause": "What could be causing my {} to be {}?",
        "high": "high", "low": "low",
        "repeat": "Should any of these tests be repeated, and when?",
        "next": ("Are there diet, lifestyle, or follow-up tests you would "
                 "recommend I discuss with you?"),
    },
    "hi": {
        "cause": "मेरा {} {} क्यों है?",
        "high": "अधिक", "low": "कम",
        "repeat": "क्या इनमें से कोई टेस्ट दोहराया जाना चाहिए, और कब?",
        "next": ("क्या आप आहार, जीवनशैली या आगे के टेस्ट के बारे में कुछ सलाह "
                 "देना चाहेंगे जिस पर मैं आपसे चर्चा कर सकूँ?"),
    },
    "mr": {
        "cause": "माझे {} {} का आहे?",
        "high": "जास्त", "low": "कमी",
        "repeat": "यापैकी कोणतीही टेस्ट पुन्हा करावी लागेल का, आणि केव्हा?",
        "next": ("आहार, जीवनशैली किंवा पुढील टेस्टबद्दल तुम्ही काही सुचवाल का "
                 "ज्यावर मी तुमच्याशी चर्चा करू शकेन?"),
    },
}

LANG_INSTRUCTION = {
    "en": "",
    "hi": "Respond entirely in Hindi, using Devanagari script.",
    "mr": "Respond entirely in Marathi, using Devanagari script.",
}


@app.after_request
def allow_frontend(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


def _find_explicit_range(text_after):
    """Use ONLY the first parenthesised group after the value, e.g. (70-99)
    or (<200). Later groups belong to other tests on following lines."""
    snippet = text_after[:40]
    m = re.search(r"\(\s*([^)]*)\)", snippet)
    if not m:
        return None
    inner = m.group(1).strip()
    m2 = re.match(r"([0-9.]+)\s*-\s*([0-9.]+)$", inner)
    if m2:
        return float(m2.group(1)), float(m2.group(2))
    m2 = re.match(r"<\s*([0-9.]+)$", inner)
    if m2:
        return None, float(m2.group(1))
    m2 = re.match(r">\s*([0-9.]+)$", inner)
    if m2:
        return float(m2.group(1)), None
    return None


def parse_lab_text(text):
    """Find known markers in pasted text and flag each value."""
    lowered = text.lower()
    results = []
    found_keys = set()
    for marker in MARKERS:
        # "Glucose" on its own must not double-count "Fasting Glucose".
        if marker["key"] == "glucose" and "fasting_glucose" in found_keys:
            continue
        pattern = r"(?:%s)[^0-9\n]{0,25}?([0-9]+\.?[0-9]*)" % "|".join(marker["aliases"])
        m = re.search(pattern, lowered)
        if not m:
            continue
        value = float(m.group(1))
        found_keys.add(marker["key"])
        low, high = marker["low"], marker["high"]
        range_source = "typical adult range"
        explicit = _find_explicit_range(lowered[m.end():])
        if explicit:
            low, high = explicit
            range_source = "range printed in your report"
        if low is not None and value < low:
            status = "low"
        elif high is not None and value > high:
            status = "high"
        else:
            status = "normal"
        results.append({
            "name": marker["label"],
            "value": value,
            "unit": marker["unit"],
            "low": low,
            "high": high,
            "range_source": range_source,
            "status": status,
            "meaning": marker["meaning"],
        })
    return results


def questions_for_doctor(results, lang="en"):
    """Concrete questions for the next visit — never advice, never diagnosis."""
    t = QUESTION_TEXT.get(lang, QUESTION_TEXT["en"])
    questions = []
    abnormal = [r for r in results if r["status"] in ("low", "high")]
    for r in abnormal[:3]:
        questions.append(t["cause"].format(r["name"].lower(), t[r["status"]]))
    questions.append(t["repeat"])
    questions.append(t["next"])
    return questions


def ollama_summary(results, lang="en"):
    """Optional plain-language summary from local Ollama. Strict prompt:
    explain ranges, never diagnose. Returns (text, True) or (None, False)."""
    lines = []
    for r in results:
        lines.append("- {}: {} {} ({}; range {}–{})".format(
            r["name"], r["value"], r["unit"], r["status"], r["low"], r["high"]))
    system = (
        "You are a health-information assistant. You must NOT diagnose "
        "any person or suggest any treatment or medicine. Explain lab "
        "results in plain, simple language: what each test measures, "
        "and what a high or low value can generally be associated with, "
        "without saying what it means for this person. End with exactly: "
        "'This is educational information only, not medical advice. "
        "Please discuss your results with your doctor.'")
    if lang in LANG_INSTRUCTION and LANG_INSTRUCTION[lang]:
        system += " " + LANG_INSTRUCTION[lang]
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": (
                "Here are lab results to explain in plain language:\n" + "\n".join(lines))},
        ],
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["message"]["content"].strip(), True
    except Exception:
        return None, False


# ---------------- Upload: every document format ----------------

def _extract_docx(data):
    """Read text from a .docx file using only the standard library.
    A .docx is a zip; the words live in word/document.xml as <w:t> nodes."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml_bytes = z.read("word/document.xml")
    except Exception:
        raise ValueError("That Word file could not be read.")
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    root = ET.fromstring(xml_bytes)
    lines = []
    for para in root.iter(w + "p"):
        text = "".join(t.text or "" for t in para.iter(w + "t"))
        if text.strip():
            lines.append(text)
    return "\n".join(lines)


def _extract_pdf(data):
    """Read text from a PDF. Needs: pip install pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ValueError("PDF support needs one install: pip install pypdf")
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages]
    except Exception:
        raise ValueError("That PDF could not be read.")
    return "\n".join(pages)


def _extract_image(data):
    """Read text from a photo/scan with OCR. Needs tesseract installed:
    pip install pillow pytesseract, plus the Tesseract program itself."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        raise ValueError("Photo reading needs: pip install pillow pytesseract, "
                         "plus the Tesseract program on your PC.")
    try:
        image = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(image)
    except Exception:
        raise ValueError("That image could not be read. If the photo is blurry, "
                         "try a clearer photo or paste the text instead.")


def extract_upload(filename, data):
    """Return the text inside an uploaded report, whatever its format."""
    name = (filename or "").lower()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="replace")
    if name.endswith(".docx"):
        return _extract_docx(data)
    if name.endswith(".pdf"):
        return _extract_pdf(data)
    if name.endswith((".png", ".jpg", ".jpeg")):
        return _extract_image(data)
    raise ValueError("Unsupported format. Upload a .txt, .pdf, .docx, "
                     "or an image (.png / .jpg).")


@app.route("/", methods=["GET"])
def health():
    """Simple health check for hosting platforms (Render, etc.)."""
    return jsonify({"status": "ok", "service": "lab-report-translator"})


@app.route("/upload", methods=["POST"])
def upload():
    """Accept one uploaded report file and return its text for analysis.
    Nothing is saved: the file is read in memory and forgotten."""
    if "file" not in request.files:
        return jsonify({"error": "No file was uploaded."}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file was uploaded."}), 400
    try:
        text = extract_upload(f.filename, f.read())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not text.strip():
        return jsonify({"error": "No readable text was found in that file. "
                                 "Try a clearer file or paste the text."}), 400
    return jsonify({"text": text})


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    lang = data.get("lang", "en")
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    if not text.strip():
        return jsonify({"error": "Please paste or upload a lab report first."}), 400
    results = parse_lab_text(text)
    if not results:
        return jsonify({
            "error": "No common lab markers were found in that text. "
                     "Try the sample report, or paste text with test names and values.",
        }), 400
    summary, used_llm = ollama_summary(results, lang)
    return jsonify({
        "results": results,
        "abnormal_count": sum(1 for r in results if r["status"] != "normal"),
        "questions": questions_for_doctor(results, lang),
        "ai_summary": summary,
        "used_llm": used_llm,
        "lang": lang,
    })


if __name__ == "__main__":
    # Locally: http://127.0.0.1:5000 with debug on. On a host like Render,
    # PORT is set by the platform: bind all interfaces, no debug.
    port = int(os.environ.get("PORT", 5000))
    on_platform = "PORT" in os.environ
    app.run(host="0.0.0.0" if on_platform else "127.0.0.1",
            port=port, debug=not on_platform)
