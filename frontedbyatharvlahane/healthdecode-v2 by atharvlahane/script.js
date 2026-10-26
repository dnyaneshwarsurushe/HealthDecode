const fileInput = document.getElementById("pdfFile");
const dropZone = document.getElementById("dropZone");
const fileMessage = document.getElementById("fileMessage");
const API_BASE_URL = "https://lab-report-translator-xeqi.onrender.com";
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

function showMessage(message, isError = false) {
    fileMessage.textContent = message;
    fileMessage.style.color = isError ? "#ff9999" : "#65f0b4";
    fileMessage.style.animation = "none";
    // Restart the small feedback animation
    void fileMessage.offsetWidth;
    fileMessage.style.animation = "fadeUp 0.35s ease";
}

async function analyzeFile(file) {
    try {
        showMessage("Uploading your report to the live backend…");
        const formData = new FormData();
        formData.append("file", file);
        const uploadResponse = await fetch(`${API_BASE_URL}/upload`, {
            method: "POST",
            body: formData
        });
        const uploadData = await uploadResponse.json().catch(() => ({}));
        if (!uploadResponse.ok || !uploadData.text) {
            throw new Error(uploadData.error || "The backend could not read that PDF.");
        }
        showMessage("Analysing your report…");
        const analyzeResponse = await fetch(`${API_BASE_URL}/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: uploadData.text, lang: "en" })
        });
        const analyzeData = await analyzeResponse.json().catch(() => ({}));
        if (!analyzeResponse.ok || !analyzeData.results) {
            throw new Error(analyzeData.error || "The backend could not analyse that report.");
        }
        const lines = analyzeData.results.map(result =>
            `${result.name}: ${result.value} ${result.unit} (${result.status}) - ${result.meaning}`
        ).join(" ");
        const questions = (analyzeData.questions || []).length
            ? ` Questions to ask your doctor: ${analyzeData.questions.join(" ")}`
            : "";
        showMessage(`Analysis: ${lines}${questions}`);
    } catch (error) {
        showMessage(`Could not analyse this report: ${error.message}`, true);
    }
}

function handleFile(file) {
    if (!file) return;
    const isPDF =
        file.type === "application/pdf" ||
        file.name.toLowerCase().endsWith(".pdf");
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
    showMessage(`Selected: ${file.name} (${sizeInMB} MB). Sending it to the live backend…`);
    analyzeFile(file);
}

fileInput.addEventListener("change", function () {
    handleFile(this.files[0]);
});

// Drag-and-drop interactions
["dragenter", "dragover"].forEach(eventName => {
    dropZone.addEventListener(eventName, event => {
        event.preventDefault();
        dropZone.classList.add("dragging");
    });
});
["dragleave", "drop"].forEach(eventName => {
    dropZone.addEventListener(eventName, event => {
        event.preventDefault();
        dropZone.classList.remove("dragging");
    });
});
dropZone.addEventListener("drop", event => {
    const file = event.dataTransfer.files[0];
    if (!file) return;
    // Use the same validation as the normal file picker
    handleFile(file);
});

// Make the drop area respond to keyboard focus and clicks
dropZone.setAttribute("tabindex", "0");
dropZone.setAttribute("role", "region");
dropZone.setAttribute("aria-label", "PDF upload area");
dropZone.addEventListener("keydown", event => {
    if (event.target !== dropZone) return;
    if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        fileInput.click();
    }
});

console.log("HealthDecode interface loaded successfully.");
