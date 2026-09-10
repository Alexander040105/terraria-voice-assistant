# AI Agent Context: Terraria RAG Voice Assistant Rebuild

Use this document as the source of truth when helping build this project. It reflects a set of already-made decisions — don't re-litigate them (e.g. "should we use Ollama?") unless something below is genuinely blocking.

---

## 1. Project Summary

Rebuilding an existing project (`github.com/Alexander040105/terraria-voice-assistant`) from scratch. It's a voice-controlled RAG assistant that answers Terraria questions (items, bosses, mechanics) while the user is actively playing the game.

**The original version's core problem:** it used Python's `SpeechRecognition` library, which does single-shot "listen, then recognize" calls (typically via Google's Web Speech API) — no real streaming, no VAD, blocks while playing, requires internet. This rebuild replaces that entire approach.

## 2. Hard Constraints

- **Fully offline at runtime** — no API keys, no calls home, works in airplane mode after first setup
- **No GPU required** — must run acceptably on integrated graphics
- **Low-end CPU friendly** — dual/quad-core, no assumptions about AVX-512 or similar
- **Must not lag Terraria** — the game is already CPU-bound on world simulation; the assistant runs in the background without causing frame drops
- **Continuous, natural speech** — not push-to-talk single-shot; VAD-driven segmentation so the user can just talk
- **Zero setup for end users** — one installer, one icon, no "install Python" or "install Ollama" step
- **Small installer, not a small app** — installer should be light (~150-250MB); models download once on first launch and are cached forever after (see Section 6)

## 3. Chosen Stack (and why)

| Layer | Choice | Why |
|---|---|---|
| Desktop frontend | ElectronJS | Wraps the same React build as the web version; adds native shell (global hotkeys, always-on-top overlay) needed to work while Terraria has focus |
| Web frontend | ReactJS (same codebase as Electron's renderer) | One React app, two shells |
| Backend | FastAPI + `uvicorn[standard]` | Async WebSocket handling; bundles cleanly into a standalone exe |
| STT | `faster-whisper`, model size `tiny.en` or `base.en` | CTranslate2-based, no PyTorch dependency, fast enough on CPU; `tiny.en` chosen specifically for low-end hardware |
| VAD | Silero VAD, **ONNX** export, via `onnxruntime` | ~2MB, torch-free, accurate speech/silence segmentation — this is what makes it "continuous" instead of push-to-talk |
| Embeddings | `nomic-embed-text-v1.5` (GGUF) via `llama-cpp-python` | Reuses the same inference engine as the LLM; avoids adding `sentence-transformers` + PyTorch as a second heavy dependency |
| LLM | `Qwen2.5-1.5B-Instruct` (GGUF, Q4_K_M) via `llama-cpp-python` | Best instruction-following at this size for CPU-only inference; primary model |
| LLM fallback (weak hardware) | `Llama-3.2-1B-Instruct` (GGUF, Q4_K_M) | Auto-selected if hardware detection finds <4 cores or <8GB RAM |
| Vector store | `sqlite-vec` | Single-file SQLite extension, minimal footprint vs. Chroma's full dependency tree — sufficient for the size of the Terraria wiki dataset |
| TTS | Piper (local, ONNX voices) | Fully offline, small models (~20-60MB/voice), fast on CPU |
| Packaging (backend) | PyInstaller (or Nuitka) | Bundles the Python backend as a standalone exe — end users never install Python |
| Packaging (app) | electron-builder | Produces the final installer, bundles the backend exe as an extra resource |

**Deliberately avoided across the whole stack:** PyTorch/CUDA (in any form — including the torch build of Silero VAD or `sentence-transformers`), Ollama as a required separate service, Chroma's full dependency chain, any cloud STT/TTS/LLM API.

**Ollama was considered and rejected** for the shipped product: it requires a separate install step, runs its own background service, and breaks the "one icon, it just works" requirement. `llama-cpp-python` uses the same underlying llama.cpp engine without the extra service layer. (Mentioning this so the agent doesn't suggest reintroducing Ollama later.)

## 4. Architecture Diagram

```
┌───────────────────────────────────────────┐
│              Electron Shell                │
│  ┌───────────────────────────────────────┐ │
│  │   React UI (same build for web too)    │ │
│  │   - mic capture (AudioWorklet)         │ │
│  │   - transcript / answer display        │ │
│  │   - audio playback                     │ │
│  └───────────────┬─────────────────────────┘│
│                  │ WebSocket (localhost)     │
└──────────────────┼───────────────────────────┘
                    ▼
┌───────────────────────────────────────────┐
│     Bundled Python Backend (PyInstaller)    │
│                                             │
│  FastAPI + WS handler                      │
│   ├─ onnxruntime → Silero VAD (segment)    │
│   ├─ faster-whisper (tiny/base) → STT      │
│   ├─ llama-cpp-python                      │
│   │    ├─ nomic-embed-text (GGUF) → embed  │
│   │    └─ Qwen2.5-1.5B-Instruct (GGUF)     │
│   │         → generation                    │
│   ├─ sqlite-vec → vector store (Terraria    │
│   │    wiki chunks, pre-built at build time)│
│   └─ Piper TTS → voice response             │
└───────────────────────────────────────────┘
```

**Critical mental model — do not get this backwards:** JS/Electron/React never performs speech-to-text. JS's only audio job is capturing raw PCM and streaming it over WebSocket. All of VAD, STT, retrieval, LLM generation, and TTS happen in the Python/FastAPI backend. If a suggested approach has JS producing "text" from the mic, that's wrong — it's reintroducing the browser's Web Speech API, which is the exact thing being replaced.

## 5. Audio Pipeline — Frontend to Backend Contract

**Frontend responsibility:** capture mic audio via `AudioWorkletNode` (not `MediaRecorder` — that compresses to webm/opus and complicates server-side decoding), convert Float32 samples to Int16 PCM at 16kHz (Whisper/VAD's expected rate), stream raw bytes over WebSocket. Receive back either JSON text messages (transcript/answer) or binary audio (TTS response) and play/display accordingly.

```js
// audio-processor.js — AudioWorklet, runs off the main thread
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0][0];
    if (channel) {
      const int16 = new Int16Array(channel.length);
      for (let i = 0; i < channel.length; i++) {
        int16[i] = Math.max(-32768, Math.min(32767, channel[i] * 32768));
      }
      this.port.postMessage(int16.buffer, [int16.buffer]);
    }
    return true;
  }
}
registerProcessor('pcm-processor', PCMProcessor);
```

```js
// React side
const ws = new WebSocket('ws://localhost:8000/ws/voice');
ws.binaryType = 'arraybuffer';

const audioCtx = new AudioContext({ sampleRate: 16000 });
await audioCtx.audioWorklet.addModule('audio-processor.js');
const mic = audioCtx.createMediaStreamSource(
  await navigator.mediaDevices.getUserMedia({ audio: true })
);
const node = new AudioWorkletNode(audioCtx, 'pcm-processor');
node.port.onmessage = (e) => {
  if (ws.readyState === WebSocket.OPEN) ws.send(e.data); // raw Int16 PCM
};
mic.connect(node);

ws.onmessage = (event) => {
  if (typeof event.data === 'string') {
    const msg = JSON.parse(event.data);   // { transcript, answer }
    setTranscript(msg.transcript);
    setAnswer(msg.answer);
  } else {
    playAudioBuffer(event.data);          // binary TTS audio
  }
};
```

**Backend responsibility:** receive raw PCM chunks, run VAD to detect speech start/end, buffer during speech, on speech-end run Whisper → RAG retrieval → LLM generation → Piper TTS, and stream results back (JSON for text, binary for audio).

```python
# main.py
from fastapi import FastAPI, WebSocket
import numpy as np

app = FastAPI()

@app.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket):
    await websocket.accept()
    audio_buffer = bytearray()
    in_speech = False

    try:
        while True:
            chunk = await websocket.receive_bytes()
            samples = np.frombuffer(chunk, dtype=np.int16)

            is_speech = vad.is_speech(samples)
            if is_speech:
                in_speech = True
                audio_buffer.extend(chunk)
            elif in_speech and not is_speech:
                text = whisper_model.transcribe(bytes(audio_buffer))
                await websocket.send_json({"transcript": text, "answer": None})

                context = retriever.query(text, top_k=3)
                answer = llm.generate(text, context)
                await websocket.send_json({"transcript": text, "answer": answer})

                answer_audio = tts.synthesize(answer)
                await websocket.send_bytes(answer_audio)

                audio_buffer.clear()
                in_speech = False
    except Exception:
        await websocket.close()
```

## 6. Model Distribution Strategy (why the installer stays small)

Do **not** bundle GGUF/ONNX model files inside the installer. Instead:

1. Ship a light installer (Electron + bundled Python backend, no models, ~150-250MB)
2. On first launch, show a "Setting up your assistant…" screen with a progress bar
3. Download in order: Qwen2.5-1.5B-Instruct GGUF, nomic-embed GGUF, Piper voice, faster-whisper `tiny.en` weights — from Hugging Face or a GitHub Releases page
4. Verify each file with a SHA256 checksum before use
5. Store in an OS app-data folder (e.g. `%APPDATA%/TerrariaAssistant/models`), not the install directory, so app updates don't re-trigger downloads
6. On subsequent launches, check "files exist + checksum passes" and skip straight to loading — no internet needed again

Further size reduction: quantize at Q4_K_M (don't go lower unless specifically targeting very old hardware — quality drops noticeably below Q4), ship exactly one Whisper size and one TTS voice by default (not a selectable library), strip unused PyInstaller modules, UPX-compress the backend exe, use electron-builder differential updates for future app updates.

## 7. Low-End-CPU Performance Rules

1. Detect hardware (core count, RAM) once at first launch; store a profile (`low`/`mid`/`high`) that selects LLM size, Whisper size, and thread count
2. Cap `llama-cpp-python` / `faster-whisper` threads to `max(1, cpu_count - 2)` — never let inference starve the game's threads
3. Launch the backend process at below-normal OS priority (e.g. via `psutil`) so the scheduler favors Terraria under contention
4. Cap LLM context window to ~1024-2048 tokens — RAG answers about game mechanics don't need long context, and smaller context means faster prompt processing
5. Limit retrieval to top-3 chunks — enough for factual Terraria Q&A, keeps prompts (and latency) small
6. Stream LLM tokens to TTS/UI as generated, not after the full response — perceived latency matters more than total latency
7. Load all models once at backend startup and keep them warm — never reload per-request
8. Ship the finished vector index (`terraria.db`) as a build artifact — never scrape or embed the wiki on the user's machine
9. If measured latency exceeds a threshold, automatically fall back to the lighter model tier rather than letting requests queue up

## 8. Project Structure

```
terraria-voice-assistant/
├── frontend/                  # React app (shared by Electron + web)
│   ├── src/
│   │   ├── audio/              # AudioWorklet capture, playback
│   │   ├── components/
│   │   └── ws-client.ts
│   └── vite.config.ts
├── electron/
│   ├── main.js                 # spawns backend exe, creates window, globalShortcut
│   └── preload.js
├── backend/
│   ├── main.py                  # FastAPI app + WS endpoint
│   ├── audio/
│   │   ├── vad.py               # Silero ONNX VAD wrapper
│   │   └── stt.py               # faster-whisper wrapper
│   ├── rag/
│   │   ├── embed.py             # nomic-embed via llama-cpp-python
│   │   ├── retriever.py         # sqlite-vec query
│   │   └── llm.py               # Qwen2.5 generation via llama-cpp-python
│   ├── tts/
│   │   └── piper_tts.py
│   ├── models/                  # bundled GGUF/ONNX model files (gitignored)
│   └── data/
│       └── terraria.db          # pre-built sqlite-vec index
├── build_scripts/
│   ├── scrape_and_embed.py      # existing scraper + vector.py, build-time only
│   └── build_backend.spec       # PyInstaller spec
└── requirements.txt
```

**Backend `requirements.txt`:**
```
fastapi
uvicorn[standard]
llama-cpp-python
faster-whisper
onnxruntime
sqlite-vec
numpy
psutil
```
(No `torch`, no `sentence-transformers`, no `chromadb` — deliberately, per Section 3.)

## 9. Build-Time vs Runtime Split

| Step | When | Where |
|---|---|---|
| Scrape Terraria wiki | Build time (once, before shipping) | `build_scripts/scrape_and_embed.py` |
| Chunk + embed pages | Build time | Same script → writes `data/terraria.db` |
| Ship `terraria.db` + GGUF/ONNX models | Build time (models) / first-launch download (per Section 6) | Bundled / downloaded |
| VAD → STT → retrieve → generate → TTS | Runtime, user's PC | Fully local, no network |

## 10. Step-by-Step Build Order

1. **Environment setup** — Python venv with the backend deps; `npm create vite@latest frontend -- --template react-ts`; `npm install -D electron electron-builder`
2. **Get models for local dev** — Qwen2.5-1.5B-Instruct GGUF (Q4_K_M), nomic-embed-text-v1.5 GGUF, a Piper voice (`.onnx` + `.onnx.json`), faster-whisper `tiny.en`. Keep out of git.
3. **Build and validate the core pipeline headless first** — one script: mic → VAD → Whisper → retrieval → LLM → Piper, printed/played to speakers. Don't touch FastAPI or Electron until latency feels acceptable.
4. **Build the Terraria knowledge base** — run the scraper, chunk, embed, write `terraria.db`. Build-time only, never on the user's machine.
5. **Wrap the pipeline in FastAPI** — one WebSocket endpoint per Section 5. Test with a bare HTML page before building the real UI.
6. **Build the React UI** — mic capture, WS client, transcript/answer display, audio playback. Test standalone in a browser tab first.
7. **Wrap in Electron** — spawn the backend (dev-mode Python process first), load the React build, add `globalShortcut` for push-to-talk, manage backend lifecycle.
8. **Add the first-launch model-download flow** — implement Section 6's checksum-verified download before packaging; easier to debug in dev mode.
9. **Package the backend** — `pyinstaller --onefile --name assistant-backend backend/main.py`, with `--hidden-import` flags as needed for `llama-cpp-python`/`onnxruntime`. Test the exe standalone first.
10. **Package the full app** — `npm run build` then `electron-builder`, with the backend exe wired in via `extraResources` (models excluded — those come from step 8's flow).
11. **Test on genuinely low-end hardware** — not the dev machine; an old laptop or a 2 vCPU/4GB cloud VM with no GPU. Confirm hardware-profile auto-detection actually downshifts and that Terraria's frame time isn't affected while idle-listening.
12. **Distribute** — GitHub Releases (free, versioned) or itch.io (download analytics, more "product" presentation).

## 11. Validation Checklist

- [ ] Runs with no internet connection at all (airplane mode test, after first-run setup)
- [ ] Tested on a machine with no dedicated GPU
- [ ] Tested on a 2-4 core CPU, measuring Terraria's frame-time impact both idle-listening and actively answering
- [ ] Cold start (model loading) time measured and acceptable
- [ ] End-to-end latency (speak → hear answer) measured for a typical question
- [ ] Confirmed no PyTorch/CUDA anywhere in the final bundled dependency tree
- [ ] Installer produces a working app with zero manual setup steps beyond the first-run model download
