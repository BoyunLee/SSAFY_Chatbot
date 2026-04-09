const API_BASE_URL = "http://localhost:8000";
const CHAT_API_URL = `${API_BASE_URL}/chat`;
const UPLOAD_API_URL = `${API_BASE_URL}/upload`;

const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const chatWindow = document.getElementById("chat-window");
const sendButton = document.getElementById("send-button");
const statusMessage = document.getElementById("status-message");

const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const uploadButton = document.getElementById("upload-button");
const uploadStatus = document.getElementById("upload-status");

function appendMessage(type, text, metaLines = []) {
    const messageElement = document.createElement("div");
    messageElement.className = `message ${type}`;

    const textElement = document.createElement("p");
    textElement.className = "message-text";
    textElement.textContent = text;
    messageElement.appendChild(textElement);

    metaLines
        .filter(Boolean)
        .forEach((line) => {
            const metaElement = document.createElement("p");
            metaElement.className = "message-meta";
            metaElement.textContent = line;
            messageElement.appendChild(metaElement);
        });

    chatWindow.appendChild(messageElement);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function setChatPendingState(isPending) {
    sendButton.disabled = isPending;
    userInput.disabled = isPending;
    statusMessage.textContent = isPending ? "AI가 문서를 검색하고 답변을 생성하고 있습니다..." : "";
}

function setUploadPendingState(isPending) {
    uploadButton.disabled = isPending;
    fileInput.disabled = isPending;
    uploadStatus.textContent = isPending ? "문서를 업로드하고 인덱싱하고 있습니다..." : "";
}

async function parseJsonResponse(response) {
    try {
        return await response.json();
    } catch (error) {
        return {};
    }
}

async function sendMessage(message) {
    const response = await fetch(CHAT_API_URL, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ message }),
    });

    const payload = await parseJsonResponse(response);
    if (!response.ok) {
        const errorMessage = payload.detail || "서버 요청 처리 중 오류가 발생했습니다.";
        throw new Error(errorMessage);
    }

    return payload;
}

async function uploadDocument(file) {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(UPLOAD_API_URL, {
        method: "POST",
        body: formData,
    });

    const payload = await parseJsonResponse(response);
    if (!response.ok) {
        const errorMessage = payload.detail || "문서 업로드 중 오류가 발생했습니다.";
        throw new Error(errorMessage);
    }

    return payload;
}

uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const file = fileInput.files[0];
    if (!file) {
        uploadStatus.textContent = "업로드할 문서를 선택해 주세요.";
        return;
    }

    setUploadPendingState(true);

    try {
        const data = await uploadDocument(file);
        uploadStatus.textContent = data.message;
        appendMessage(
            "bot",
            `${data.filename} 문서를 학습 대상으로 추가했습니다.`,
            [
                `생성된 청크 수: ${data.chunks_added}`,
                `현재 문서 수: ${data.documents}, 전체 청크 수: ${data.chunks}`,
            ],
        );
        uploadForm.reset();
    } catch (error) {
        uploadStatus.textContent = error.message;
        appendMessage("bot", `문서 업로드에 실패했습니다. ${error.message}`);
    } finally {
        setUploadPendingState(false);
    }
});

chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = userInput.value.trim();
    if (!message) {
        statusMessage.textContent = "질문을 입력해 주세요.";
        userInput.focus();
        return;
    }

    appendMessage("user", message);
    userInput.value = "";
    setChatPendingState(true);

    try {
        const data = await sendMessage(message);
        const metaLines = [
            data.reference_note,
            data.sources?.length ? `참고 문서: ${data.sources.join(", ")}` : "참고 문서 없음",
            `유사도 기준: ${data.similarity_threshold}, 청크 크기: ${data.chunk_size}, 오버랩: ${data.chunk_overlap}`,
        ];
        appendMessage("bot", data.answer || "응답이 비어 있습니다.", metaLines);
    } catch (error) {
        appendMessage("bot", `오류가 발생했습니다. ${error.message}`);
    } finally {
        setChatPendingState(false);
        userInput.focus();
    }
});
