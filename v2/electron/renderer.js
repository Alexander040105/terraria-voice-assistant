const startListening = document.getElementById('start_listening');
const answer = document.getElementById('answer');
startListening.addEventListener('click', async () => {
    try {
        const res = await fetch("http://127.0.0.1:8000/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: "what is the eye of cthulu" }),
        });

        const data = await res.json();
        answer.textContent = data.answer;
    } catch (err) {
        console.error(err);
    }
});

