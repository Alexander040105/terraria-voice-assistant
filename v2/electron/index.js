const { app, BrowserWindow } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

const projectRoot = path.resolve(__dirname, "..");
const projectRootParent = path.resolve(__dirname, "../..");

const python = spawn(
    path.join(projectRootParent, ".venv", "Scripts", "python.exe"),
    ["backend/main.py"],
    {
        cwd: projectRoot,
        windowsHide: true,
    }
);

python.stdout.on("data", (data) => {
    console.log("Python:", data.toString());
});

python.stderr.on("data", (data) => {
    console.error("Python error:", data.toString());
});

python.on("close", (code) => {
    console.log(`Python process exited with code ${code}`);
});

function createWindow() {
    const win = new BrowserWindow({
            width: 400,
            height: 250,
            frame: false,
            transparent: true,
            webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            nodeIntegration: false,
            contextIsolation: true,
        },
    });

    win.loadFile(path.join(__dirname, "index.html"));
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
});
