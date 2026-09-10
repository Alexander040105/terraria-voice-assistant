const { app, BrowserWindow, globalShortcut, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");

const projectRoot = path.resolve(__dirname, "..");
const projectRootParent = path.resolve(__dirname, "../..");
const backendPortFile = path.join(projectRoot, "backend", "runtime_port.txt");

function getBackendPort() {
    if (process.env.TERRARIA_ASSISTANT_PORT) {
        return process.env.TERRARIA_ASSISTANT_PORT;
    }

    try {
        if (fs.existsSync(backendPortFile)) {
            const value = fs.readFileSync(backendPortFile, "utf-8").trim();
            if (value) {
                return value;
            }
        }
    } catch (error) {
        console.warn("Failed to read backend port file:", error);
    }

    return "8765";
}

function getBackendBaseUrl() {
    return `http://127.0.0.1:${getBackendPort()}`;
}

function getBackendBaseUrlWithFallback() {
    const primary = getBackendBaseUrl();
    try {
        if (fs.existsSync(backendPortFile)) {
            const value = fs.readFileSync(backendPortFile, "utf-8").trim();
            if (value && !primary.endsWith(`:${value}`)) {
                return [primary, `http://127.0.0.1:${value}`];
            }
        }
    } catch (error) {
        console.warn("Failed to read backend port file:", error);
    }
    return [primary];
}

let backendProcess = null;
let mainWindow = null;
const pushToTalkShortcut = process.env.TERRARIA_PTT_HOTKEY || "CommandOrControl+Shift+Space";

function resolveBackendCommand() {
    if (app.isPackaged) {
        return {
            command: path.join(process.resourcesPath, "backend", "terraria_assistant.exe"),
            args: [],
            cwd: process.resourcesPath,
        };
    }

    const v2Venv = path.join(projectRoot, ".venv", "Scripts", "python.exe");
    const rootVenv = path.join(projectRootParent, ".venv", "Scripts", "python.exe");
    let command = "python";
    if (fs.existsSync(v2Venv)) {
        command = v2Venv;
    } else if (fs.existsSync(rootVenv)) {
        command = rootVenv;
    }

    return {
        command,
        args: ["backend/main.py"],
        cwd: projectRoot,
    };
}

async function checkBackendHealth() {
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 1200);
        const res = await fetch(`${getBackendBaseUrl()}/health`, {
            signal: controller.signal,
        });
        clearTimeout(timeout);
        return res.ok;
    } catch (error) {
        return false;
    }
}

async function waitForBackend(timeoutMs = 8000, intervalMs = 400) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
        if (await checkBackendHealth()) {
            return true;
        }
        await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
    return false;
}

async function startBackend() {
    const alreadyRunning = await checkBackendHealth();
    if (alreadyRunning) {
        console.log("Backend already running; skipping spawn.");
        return;
    }

    const { command, args, cwd } = resolveBackendCommand();
    const backendPort = getBackendPort();
    backendProcess = spawn(command, args, {
        cwd,
        windowsHide: true,
        env: {
            ...process.env,
            TERRARIA_ASSISTANT_PORT: backendPort,
            TERRARIA_CHAT_MODEL: process.env.TERRARIA_CHAT_MODEL || "qwen2.5:1.5b",
            TERRARIA_EMBED_MODEL: process.env.TERRARIA_EMBED_MODEL || "nomic-embed-text",
            TERRARIA_RERANKER_MODEL:
                process.env.TERRARIA_RERANKER_MODEL || "cross-encoder/ms-marco-MiniLM-L-6-v2",
        },
    });

    backendProcess.stdout.on("data", (data) => {
        console.log("Backend:", data.toString());
    });

    backendProcess.stderr.on("data", (data) => {
        console.error("Backend error:", data.toString());
    });

    backendProcess.on("close", (code) => {
        console.log(`Backend process exited with code ${code}`);
    });

    const ready = await waitForBackend();
    if (!ready) {
        console.warn("Backend did not become ready within timeout.");
    }
}

function stopBackend() {
    if (!backendProcess) return;
    backendProcess.kill();
    backendProcess = null;
}

function createWindow() {
    const win = new BrowserWindow({
        width: 520,
        height: 360,
        minWidth: 420,
        minHeight: 300,
        frame: false,
        transparent: true,
        resizable: true,
        alwaysOnTop: true,
        backgroundColor: "#00000000",
        webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            nodeIntegration: false,
            contextIsolation: true,
        },
    });

    win.loadFile(path.join(__dirname, "index.html"));
    mainWindow = win;
}

app.whenReady().then(async () => {
    await startBackend();
    createWindow();

    globalShortcut.register(pushToTalkShortcut, () => {
        if (!mainWindow) return;
        mainWindow.webContents.send("push-to-talk");
    });
});

ipcMain.handle("api:request", async (_event, route, payload, method = "GET") => {
    const options = {
        method,
        headers: { "Content-Type": "application/json" },
    };

    if (payload && method !== "GET") {
        options.body = JSON.stringify(payload);
    }

    const timeoutMs = route === "/ask" || route === "/listen" ? 60000 : 5000;
    let lastError = null;
    for (let attempt = 0; attempt < 3; attempt += 1) {
        const baseUrls = getBackendBaseUrlWithFallback();
        for (const baseUrl of baseUrls) {
            const url = `${baseUrl}${route}`;
            try {
                const controller = new AbortController();
                const timeout = setTimeout(() => controller.abort(), timeoutMs);
                const res = await fetch(url, { ...options, signal: controller.signal });
                clearTimeout(timeout);
                if (!res.ok) {
                    const text = await res.text();
                    throw new Error(`Backend ${res.status}: ${text}`);
                }
                return res.json();
            } catch (error) {
                lastError = error;
            }
        }
        await new Promise((resolve) => setTimeout(resolve, 300));
    }

    throw lastError;
});

app.on("before-quit", stopBackend);
app.on("will-quit", () => {
    globalShortcut.unregisterAll();
});

app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
});
