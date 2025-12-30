const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("api", {
    ask: async (question) => {
        const res = await fetch("http://127.0.0.1:8000/api/talk", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question }),
        });
        return res.json();
    },
});
