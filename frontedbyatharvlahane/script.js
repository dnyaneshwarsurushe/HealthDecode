const fileInput = document.getElementById("pdfFile");
const fileName = document.getElementById("fileName");
const statusMessage = document.getElementById("status");
const resultsSection = document.getElementById("resultsSection");
const resultsList = document.getElementById("resultsList");
const questionsList = document.getElementById("questionsList");
const languageSelect = document.getElementById("language");
const API_BASE_URL = "https://lab-report-translator-xeqi.onrender.com";
const REQUEST_TIMEOUT_MS = 75000;
const WAKEUP_MESSAGE_DELAY_MS = 10000;
const ALLOWED_EXTENSIONS = new Set([
    ".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".webp",
    ".bmp", ".tif", ".tiff", ".txt"
]);

class RequestError extends Error {
    constructor(message, retryable = false) {
        super(message);
        this.retryable = retryable;
    }
}

function setStatus(message, isError = false) {
    statusMessage.textContent = message;
    statusMessage.classList.toggle("status-error", isError);
}

async function requestJson(path, options, label) {
    for (let attempt = 0; attempt < 2; attempt += 1) {
        const controller = new AbortController();
        const timeout = window.setTimeout(
            () => controller.abort(),
            REQUEST_TIMEOUT_MS
        );
        const wakeupMessage = window.setTimeout(
            () => setStatus("The server is waking up, please wait..."),
            WAKEUP_MESSAGE_DELAY_MS
        );

        try {
            const response = await fetch(`${API_BASE_URL}${path}`, {
                ...options,
                signal: controller.signal
            });
            const data = await response.json().catch(() => null);

            if (!response.ok) {
                const message = data && typeof data.error === "string"
                    ? data.error
                    : `${label} failed (HTTP ${response.status}).`;
                throw new RequestError(message, response.status >= 500);
            }

            if (!data || typeof data !== "object") {
                throw new RequestError(`${label} returned an invalid response.`);
            }
            return data;
        } catch (error) {
            const retryable = error instanceof RequestError
                ? error.retryable
                : true;
            const timedOut = error.name === "AbortError";

            if (retryable && attempt === 0) {
                setStatus("The server is waking up, please wait. Retrying once...");
                continue;
            }

            if (timedOut || !(error instanceof RequestError)) {
                throw new Error(
                    "The server could not be reached after retrying. Please try again."
                );
            }
            throw error;
        } finally {
            window.clearTimeout(timeout);
            window.clearTimeout(wakeupMessage);
        }
    }

    throw new Error("The request could not be completed. Please try again.");
}

function createTextElement(tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) {
        element.className = className;
    }
    element.textContent = text;
    return element;
}

function displayResults(data) {
    if (!Array.isArray(data.results) || !Array.isArray(data.questions)) {
        throw new Error("The analysis response is missing results or questions.");
    }

    resultsList.replaceChildren();
    questionsList.replaceChildren();

    data.results.forEach((result) => {
        if (!result || typeof result !== "object") {
            throw new Error("The analysis response contains an invalid result.");
        }

        const status = String(result.status || "").toLowerCase();
        if (!["low", "normal", "high"].includes(status)) {
            throw new Error("The analysis response contains an unknown result status.");
        }

        const card = document.createElement("article");
        card.className = "result-card";
        const heading = document.createElement("div");
        heading.className = "result-heading";
        heading.append(
            createTextElement("h3", "", String(result.name ?? "Unnamed marker")),
            createTextElement("span", `status-badge status-${status}`, status === "normal" ? "Normal" : status.toUpperCase())
        );
        card.append(heading);

        const value = [result.value, result.unit]
            .filter((part) => part !== null && part !== undefined && String(part).trim())
            .join(" ");
        card.append(createTextElement("p", "result-value", value || "Value not provided"));
        card.append(createTextElement(
            "p",
            "result-meaning",
            String(result.meaning ?? "No plain-language explanation provided.")
        ));

        const rangeParts = [];
        if (result.low !== null && result.low !== undefined && String(result.low).trim()) {
            rangeParts.push(String(result.low));
        } else {
            rangeParts.push("Not provided");
        }
        rangeParts.push("–");
        if (result.high !== null && result.high !== undefined && String(result.high).trim()) {
            rangeParts.push(String(result.high));
        } else {
            rangeParts.push("Not provided");
        }
        const range = `Reference range: ${rangeParts.join(" ")}${result.unit ? ` ${result.unit}` : ""}`;
        card.append(createTextElement("p", "reference-range", range));
        resultsList.append(card);
    });

    data.questions.forEach((question) => {
        if (typeof question !== "string" || !question.trim()) {
            throw new Error("The analysis response contains an invalid doctor question.");
        }
        questionsList.append(createTextElement("li", "", question));
    });

    resultsSection.hidden = false;
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function analyzeReport(file) {
    const extension = file.name.match(/\.[^.]+$/)?.[0].toLowerCase() || "";
    if (!ALLOWED_EXTENSIONS.has(extension)) {
        setStatus("Choose a PDF, Word, image, or text file.", true);
        fileInput.value = "";
        return;
    }

    fileName.textContent = file.name;
    resultsSection.hidden = true;
    resultsList.replaceChildren();
    questionsList.replaceChildren();
    fileInput.disabled = true;

    try {
        const formData = new FormData();
        formData.append("file", file);
        setStatus("Uploading your report...");
        const uploaded = await requestJson(
            "/upload",
            { method: "POST", body: formData },
            "Report upload"
        );
        if (typeof uploaded.text !== "string" || !uploaded.text.trim()) {
            throw new Error("The server did not return any report text to analyze.");
        }

        setStatus("Analyzing your report...");
        const analysis = await requestJson(
            "/analyze",
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: uploaded.text,
                    lang: languageSelect.value
                })
            },
            "Report analysis"
        );

        displayResults(analysis);
        setStatus("Analysis complete.");
    } catch (error) {
        setStatus(error.message || "Analysis failed. Please try again.", true);
    } finally {
        fileInput.disabled = false;
    }
}

fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) {
        analyzeReport(file);
    }
});
