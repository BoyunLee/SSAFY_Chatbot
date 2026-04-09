// script_v1.js - [Step 1] 채팅 UI 만들기
// 목표: GPT 응답을 console.log 대신 HTML 화면에 예쁜 말풍선으로 표시하기
// 핵심: document.createElement()를 사용한 DOM 조작

function sendMessage() {
    const inputElement = document.getElementById("user-input");
    const userMessage = inputElement.value;

    if (userMessage === "") return;

    // [추가] 내 메시지를 화면에 표시
    addMessage("user", userMessage);

    // 입력창 비우기
    inputElement.value = "";

    // TODO: 02. localhost:8000/chat으로 post 요청을 보내자. 응답은 addMessage로 전달한다.

    // END
}


// [보너스] 엔터키로 전송하기
document.getElementById("user-input").addEventListener("keypress", function(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
});

// [핵심 함수] 화면에 메시지 추가하기
function addMessage(type, text) {
    // 1. 채팅창 요소 찾기
    const chatWindow = document.getElementById("chat-window");

    // 2. 새로운 div 태그 만들기
    // 결과물: <div></div>
    const messageDiv = document.createElement("div");

    // 3. 클래스 이름 붙이기 (CSS 스타일 적용용)
    // 결과물: <div class="message user"></div> 또는 <div class="message bot"></div>
    messageDiv.className = "message " + type;

    // 4. 텍스트 내용 넣기
    // 결과물: <div class="message user">안녕하세요</div>
    messageDiv.innerText = text;

    // 5. 채팅창에 붙이기
    chatWindow.appendChild(messageDiv);

    // 6. 스크롤을 맨 아래로 (새 메시지가 보이도록)
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

