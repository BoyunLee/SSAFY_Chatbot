// script_v4.js - [Step 4] RAG 통합 채팅
// 목표: /integrated-chat 엔드포인트로 변경하여 RAG 기반 답변 받기
// 핵심 변경: URL을 /search -> /integrated-chat 로 변경! (단 한 줄!)

function sendMessage() {
    const inputElement = document.getElementById("user-input");
    const userMessage = inputElement.value;

    if (userMessage === "") return;

    addMessage("user", userMessage);
    inputElement.value = "";

    // [핵심 변경] /search 대신 /integrated-chat 사용!
    // RAG: 검색 + GPT 생성을 한 번에 처리
    fetch("http://localhost:8000/integrated-chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: userMessage })
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        // GPT가 생성한 답변 표시
        // data.answer: GPT가 문서를 참고하여 생성한 답변
        // data.source: 참고한 문서 정보
        addMessage("bot", data.answer, data.source);
    })
    .catch(function(error) {
        addMessage("bot", "서버 연결에 실패했습니다.");
    });
}

// [수정] 출처 정보도 함께 표시하도록 개선
function addMessage(type, text, source) {
    const chatWindow = document.getElementById("chat-window");
    const messageDiv = document.createElement("div");
    messageDiv.className = "message " + type;
    messageDiv.innerText = text;

    // 봇 메시지이고 출처 정보가 있으면 표시
    if (type === "bot" && source) {
        const sourceDiv = document.createElement("div");
        sourceDiv.className = "source-tag";
        sourceDiv.innerText = "출처: " + source;
        messageDiv.appendChild(sourceDiv);
    }

    chatWindow.appendChild(messageDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}
