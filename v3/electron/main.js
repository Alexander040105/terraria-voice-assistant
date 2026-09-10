const { app, BrowserWindow, globalShortcut } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const http = require('http')
const fs = require('fs')

let mainWindow
let backendProcess

const isDev = !app.isPackaged
const useDevServer = isDev && process.env.ELECTRON_DEV === '1'

function findPython() {
  const venv = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe')
  if (fs.existsSync(venv)) return venv
  const py = path.join(__dirname, '..', 'venv', 'Scripts', 'python.exe')
  if (fs.existsSync(py)) return py
  return process.platform === 'win32' ? 'py' : 'python'
}

function startBackend() {
  const cwd = path.join(__dirname, '..')
  if (isDev) {
    const python = findPython()
    console.log(`Starting backend with ${python}`)
    backendProcess = spawn(python, ['-m', 'uvicorn', 'backend.main:app', '--port', '8000'], {
      cwd,
      windowsHide: true
    })
  } else {
    const exe = path.join(process.resourcesPath, 'assistant-backend', 'assistant-backend.exe')
    backendProcess = spawn(exe, [], {
      cwd: process.resourcesPath,
      windowsHide: true
    })
  }

  if (backendProcess) {
    backendProcess.stdout.on('data', (d) => console.log(`backend: ${d}`))
    backendProcess.stderr.on('data', (d) => console.error(`backend err: ${d}`))
    backendProcess.on('exit', (code) => console.log(`backend exited with code ${code}`))
  }
}

function waitForBackend(timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    const start = Date.now()
    const check = () => {
      http.get('http://127.0.0.1:8000/health', (res) => {
        if (res.statusCode === 200) {
          resolve()
        } else {
          tryAgain()
        }
      }).on('error', tryAgain)
    }
    const tryAgain = () => {
      if (Date.now() - start > timeoutMs) {
        reject(new Error('Backend did not become healthy in time'))
        return
      }
      setTimeout(check, 250)
    }
    tryAgain()
  })
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 480,
    height: 700,
    alwaysOnTop: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true
    }
  })

  try {
    await waitForBackend()
    console.log('Backend healthy; loading UI')
  } catch (err) {
    console.error(err)
  }

  if (useDevServer) {
    await mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    await mainWindow.loadFile(path.join(__dirname, '..', 'frontend', 'dist', 'index.html'))
  }
  mainWindow.show()
}

app.whenReady().then(async () => {
  startBackend()
  await createWindow()

  globalShortcut.register('Alt+T', () => {
    if (!mainWindow) return
    if (mainWindow.isVisible()) mainWindow.hide()
    else mainWindow.show()
  })
})

app.on('window-all-closed', () => {
  if (backendProcess) backendProcess.kill()
  if (process.platform !== 'darwin') app.quit()
})

app.on('will-quit', () => {
  if (backendProcess) backendProcess.kill()
})
