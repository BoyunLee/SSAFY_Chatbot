// script_v3.js - [Step 3] 벡터 검색 결과를 채팅 UI에 표시하기
// 목표: /search API로 유사도 검색을 하고, 결과를 채팅 말풍선으로 보여주기
// 핵심 변경: fetch URL을 /chat -> /search 로 변경!

function sendMessage() {
    const inputElement = document.getElementById("user-input");
    const userMessage = inputElement.value;

    if (userMessage === "") return;

    // 내 메시지를 화면에 표시
    addMessage("user", userMessage);
    inputElement.value = "";

    // [핵심 변경] /chat 대신 /search 엔드포인트 사용!
    fetch("http://localhost:8000/search", {
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
        // 검색 결과를 화면에 표시
        // data.answer: 검색된 문서 내용
        // data.score: 유사도 점수 (0~1)
        // data.source: 출처 파일명
        addMessage("bot", data.answer);

        // (선택) 콘솔에 추가 정보 출력
        console.log("유사도 점수:", data.score);
        console.log("출처:", data.source);
    })
    .catch(function(error) {
        addMessage("bot", "서버 연결에 실패했습니다.");
    });
}
