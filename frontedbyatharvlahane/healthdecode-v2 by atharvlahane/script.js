const fileInput = document.getElementById("pdfFile");
const dropZone = document.getElementById("dropZone");
const fileMessage = document.getElementById("fileMessage");
const API_BASE_URL = "https://lab-report-translator-xeqi.onrender.com";
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const WAKE_UP_MESSAGE = "Could not reach the analysis server. The server may be waking up (it sleeps on the free plan) \u2014 please wait a minute and try again.";

function showMessage(message, isError = false) {
    if (!fileMessage) return;
    fileMessage.textContent = message;
    fileMessage.style.color = isError ? "#ff9999" : "#65f0b4";
    fileMessage.style.animation = "none";
    void fileMessage.offsetWidth;
    fileMessage.style.animation = "fadeUp 0.35s ease";
}

function ensureResultsSection() {
    let section = document.getElementById("analysisResults");
    if (section) return section;
    section = document.createElement("section");
    section.id = "analysisResults";
    section.className = "analysis-results";
    section.setAttribute("aria-live", "polite");
    const anchor = dropZone || document.querySelector(".upload-panel");
    if (anchor && anchor.parentNode) {
        anchor.parentNode.insertBefore(section, anchor.nextSibling);
    } else if (fileMessage && fileMessage.parentNode) {
        fileMessage.parentNode.appendChild(section);
    } else {
        document.body.appendChild(section);
    }
    const style = document.createElement("style");
    style.textContent = ".analysis-results{margin:22px auto 0;max-width:760px;text-align:left}.analysis-results h2{color:#f0fff8;margin:0 0 8px}.analysis-results .analysis-summary{color:#9bb8ac;margin:0 0 16px}.analysis-result{border:1px solid rgba(154,230,197,0.25);background:#102621;border-radius:14px;padding:16px;margin:0 0 14px}.analysis-result-header{display:flex;justify-content:space-between;gap:12px;align-items:center}.analysis-result-header strong{color:#f0fff8;font-size:18px}.analysis-value{color:#f0fff8;font-size:20px;font-weight:700;margin:10px 0 4px}.analysis-range{color:#9bb8ac;margin:0 0 8px}.analysis-meaning{color:#d7efe3;margin:0}.result-badge{border-radius:999px;padding:4px 12px;font-size:13px;font-weight:700;white-space:nowrap}.result-badge.low{background:#ff6b6b;color:#2b0505}.result-badge.normal{background:#65f0b4;color:#06331f}.result-badge.high{background:#ffb020;color:#3a2200}.analysis-questions{border-top:1px solid rgba(154,230,197,0.25);margin-top:20px;padding-top:16px}.analysis-questions h3{color:#f0fff8;margin:0 0 10px}.analysis-questions li{color:#d7efe3;margin:0 0 8px}.analysis-note{color:#9bb8ac;font-size:14px;margin-top:18px}";
    document.head.appendChild(style);
    return section;
}

function clearResults() {
    const section = document.getElementById("analysisResults");
    if (section) section.innerHTML = "";
}

function badgeLabel(status) {
    const value = String(status || "").toLowerCase();
    if (value === "low") return "LOW";
    if (value === "high") return "HIGH";
    return "Normal";
}

function rangeText(result) {
    const direct = result.reference_range || result.referenceRange || result.range;
    if (direct) return String(direct);
    if (result.low !== undefined && result.low !== null && result.high !== undefined && result.high !== null) {
        return result.low + "\u2013" + result.high + (result.unit ? " " + result.unit : "");
    }
    return "";
}

function renderResults(data, fileName) {
    const section = ensureResultsSection();
    section.innerHTML = "";
    const results = Array.isArray(data.results) ? data.results : [];
    const heading = document.createElement("h2");
    heading.textContent = "Your results";
    section.appendChild(heading);
    const abnormal = typeof data.abnormal_count === "number"
        ? data.abnormal_count
        : results.filter(function (r) { return String(r.status || "").toLowerCase() !== "normal"; }).length;
    const summary = document.createElement("p");
    summary.className = "analysis-summary";
    summary.textContent = fileName + ": " + results.length + " marker" + (results.length === 1 ? "" : "s") + " found, " + abnormal + " outside the reference range.";
    section.appendChild(summary);
    results.forEach(function (result) {
        const card = document.createElement("article");
        card.className = "analysis-result";
        const header = document.createElement("div");
        header.className = "analysis-result-header";
        const name = document.createElement("strong");
        name.textContent = result.name || result.label || "Marker";
        const badge = document.createElement("span");
        const status = String(result.status || result.flag || "normal").toLowerCase();
        badge.className = "result-badge " + (status === "low" || status === "high" ? status : "normal");
        badge.textContent = badgeLabel(status);
        header.appendChild(name);
        header.appendChild(badge);
        card.appendChild(header);
        const value = document.createElement("p");
        value.className = "analysis-value";
        value.textContent = result.value + (result.unit ? " " + result.unit : "");
        card.appendChild(value);
        const range = rangeText(result);
        if (range) {
            const rangeLine = document.createElement("p");
            rangeLine.className = "analysis-range";
            rangeLine.textContent = "Reference range: " + range;
            card.appendChild(rangeLine);
        }
        if (result.meaning || result.plain_meaning || result.explanation) {
            const meaning = document.createElement("p");
            meaning.className = "analysis-meaning";
            meaning.textContent = result.meaning || result.plain_meaning || result.explanation;
            card.appendChild(meaning);
        }
        section.appendChild(card);
    });
    const questions = Array.isArray(data.questions) ? data.questions : [];
    if (questions.length) {
        const block = document.createElement("div");
        block.className = "analysis-questions";
        const title = document.createElement("h3");
        title.textContent = "Questions for your doctor";
        block.appendChild(title);
        const list = document.createElement("ul");
        questions.forEach(function (question) {
            const item = document.createElement("li");
            item.textContent = question;
            list.appendChild(item);
        });
        block.appendChild(list);
        section.appendChild(block);
    }
    const note = document.createElement("p");
    note.className = "analysis-note";
    note.textContent = "This is educational information only, not medical advice and not a diagnosis. Please discuss your results with a qualified healthcare professional.";
    section.appendChild(note);
    section.scrollIntoView({ behavior: "smooth" });
}

async function analyzeFile(file) {
    try {
        showMessage("Uploading your report to the live backend\u2026");
        const formData = new FormData();
        formData.append("file", file);
        const uploadResponse = await fetch(API_BASE_URL + "/upload", { method: "POST", body: formData });
        const uploadData = await uploadResponse.json().catch(function () { return {}; });
        if (!uploadResponse.ok || !uploadData.text) {
            throw new Error(uploadData.error || uploadData.message || "The backend could not read that PDF.");
        }
        showMessage("Analysing your report\u2026");
        const analyzeResponse = await fetch(API_BASE_URL + "/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: uploadData.text, lang: "en" })
        });
        const analyzeData = await analyzeResponse.json().catch(function () { return {}; });
        if (!analyzeResponse.ok) {
            throw new Error(analyzeData.error || analyzeData.message || "The backend could not analyse that report.");
        }
        if (!Array.isArray(analyzeData.results) || analyzeData.results.length === 0) {
            clearResults();
            showMessage(analyzeData.message || analyzeData.error || "No markers were found in this report.", true);
            return;
        }
        renderResults(analyzeData, file.name);
        showMessage("Selected: " + file.name + ". Analysis complete.");
    } catch (error) {
        clearResults();
        if (error && error.name === "TypeError") {
            showMessage(WAKE_UP_MESSAGE, true);
        } else {
            showMessage("Could not analyse this report: " + (error && error.message ? error.message : "Unknown error"), true);
        }
    }
}

function handleFile(file) {
    if (!file) return;
    const isPDF = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPDF) {
        showMessage("Please choose a PDF file.", true);
        fileInput.value = "";
        return;
    }
    if (file.size > MAX_FILE_SIZE) {
        showMessage("This file is too large. Please choose a PDF under 10 MB.", true);
        fileInput.value = "";
        return;
    }
    if (file.size === 0) {
        showMessage("This file is empty. Please choose another PDF.", true);
        fileInput.value = "";
        return;
    }
    const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
    clearResults();
    showMessage("Selected: " + file.name + " (" + sizeInMB + " MB). Sending it to the live backend\u2026");
    analyzeFile(file);
}

if (fileInput) {
    fileInput.addEventListener("change", function () { handleFile(this.files[0]); });
}
if (dropZone) {
    ["dragenter", "dragover"].forEach(function (eventName) {
        dropZone.addEventListener(eventName, function (event) { event.preventDefault(); dropZone.classList.add("dragging"); });
    });
    ["dragleave", "drop"].forEach(function (eventName) {
        dropZone.addEventListener(eventName, function (event) { event.preventDefault(); dropZone.classList.remove("dragging"); });
    });
    dropZone.addEventListener("drop", function (event) {
        const file = event.dataTransfer.files[0];
        if (!file) return;
        handleFile(file);
    });
    dropZone.setAttribute("tabindex", "0");
    dropZone.setAttribute("role", "region");
    dropZone.setAttribute("aria-label", "PDF upload area");
    dropZone.addEventListener("keydown", function (event) {
        if (event.target !== dropZone) return;
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); fileInput.click(); }
    });
}
console.log("HealthDecode interface loaded successfully.");
