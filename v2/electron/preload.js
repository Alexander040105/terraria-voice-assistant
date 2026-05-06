const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
    ask: async (question) => {
        return ipcRenderer.invoke("api:request", "/ask", { question }, "POST");
    },
    status: async () => {
        return ipcRenderer.invoke("api:request", "/status", null, "GET");
    },
    health: async () => {
        return ipcRenderer.invoke("api:request", "/health", null, "GET");
    },
    init: async () => {
        return ipcRenderer.invoke("api:request", "/init", null, "POST");
    },
    listen: async () => {
        return ipcRenderer.invoke("api:request", "/listen", null, "POST");
    },
    onPushToTalk: (handler) => {
        ipcRenderer.removeAllListeners("push-to-talk");
        ipcRenderer.on("push-to-talk", handler);
    },
});
