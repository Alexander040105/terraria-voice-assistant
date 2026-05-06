# Terraria Lorekeeper Export Guide (Windows)

## 1) Build the Python backend

From the repo root:

```powershell
cd v2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r ..\requirements.txt
```

Build the backend executable:

```powershell
cd backend
pyinstaller terraria_assistant.spec
```

This creates:

```
backend\dist\terraria_assistant\terraria_assistant.exe
```

## 2) Build the Electron app

From the repo root:

```powershell
cd v2
npm install
npm run dist
```

The installer will appear in:

```
v2\dist\Terraria Lorekeeper-Setup.exe
```

## 3) Notes

- The Electron build bundles the Python backend from `backend\dist\terraria_assistant` into the app.
- If you update wiki content, rebuild the backend so the embedded scraped pages stay in sync.
- You can override models at runtime with environment variables:
  - `TERRARIA_CHAT_MODEL`
  - `TERRARIA_EMBED_MODEL`
  - `TERRARIA_RERANKER_MODEL`
  - `TERRARIA_ASSISTANT_PORT`
