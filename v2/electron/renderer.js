const form = document.getElementById("ask-form");
const input = document.getElementById("question-input");
const answerText = document.getElementById("answer-text");
const evidenceText = document.getElementById("evidence-text");
const confidenceBadge = document.getElementById("confidence-badge");
const sourceList = document.getElementById("source-list");
const statusLabel = document.getElementById("status-label");
const askButton = document.getElementById("ask-button");
const listenButton = document.getElementById("listen-button");

let statusInFlight = false;

function setLoading(isLoading) {
    askButton.disabled = isLoading;
    askButton.textContent = isLoading ? "Summoning..." : "Ask";
}

function renderSources(sources) {
    sourceList.innerHTML = "";
    if (!sources || sources.length === 0) {
        sourceList.innerHTML = "<li>No sources available.</li>";
        return;
    }

    sources.slice(0, 6).forEach((source) => {
        const item = document.createElement("li");
        const title = source.page_title || "Unknown";
        const section = source.section_title || "Overview";
        const url = source.url || "";
        item.innerHTML = `
            <div class="source-title">${title}</div>
            <div class="source-section">${section}</div>
            <a class="source-link" href="${url}" target="_blank">${url}</a>
        `;
        sourceList.appendChild(item);
    });
}

function renderHistory() {}

async function refreshStatus() {
    if (statusInFlight) {
        return;
    }
    statusInFlight = true;
    try {
        const status = await window.api.status();
        if (status.model_loaded) {
            statusLabel.textContent = "Ready";
            statusLabel.classList.add("status-ready");
        } else {
            statusLabel.textContent = "Warming up";
        }
    } catch (error) {
        statusLabel.textContent = "Offline";
        statusLabel.classList.remove("status-ready");
    } finally {
        statusInFlight = false;
    }
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;

    setLoading(true);
    answerText.textContent = "";
    evidenceText.textContent = "";
    confidenceBadge.textContent = "";

    try {
        const response = await window.api.ask(question);
        answerText.textContent = response.answer || "No answer returned.";
        evidenceText.textContent = response.evidence || "No evidence returned.";
        confidenceBadge.textContent = response.confidence || "Unknown";
        confidenceBadge.dataset.confidence = response.confidence || "Unknown";
        renderSources(response.sources || []);

    } catch (error) {
        answerText.textContent = "Something went wrong. The backend may be offline.";
        evidenceText.textContent = String(error);
        confidenceBadge.textContent = "Unavailable";
        confidenceBadge.dataset.confidence = "Unavailable";
    } finally {
        setLoading(false);
    }
});

listenButton.addEventListener("click", async () => {
    runListen();
});

async function runListen() {
    setLoading(true);
    answerText.textContent = "Listening...";
    evidenceText.textContent = "";
    confidenceBadge.textContent = "";

    try {
        const response = await window.api.listen();
        input.value = response.question || "";
        answerText.textContent = response.answer || "No answer returned.";
        evidenceText.textContent = response.evidence || "No evidence returned.";
        confidenceBadge.textContent = response.confidence || "Unknown";
        confidenceBadge.dataset.confidence = response.confidence || "Unknown";
        renderSources(response.sources || []);
    } catch (error) {
        answerText.textContent = "Listening failed. Check your microphone.";
        evidenceText.textContent = String(error);
        confidenceBadge.textContent = "Unavailable";
        confidenceBadge.dataset.confidence = "Unavailable";
    } finally {
        setLoading(false);
    }
}

refreshStatus();
setInterval(refreshStatus, 15000);

window.api.onPushToTalk(() => {
    runListen();
});

