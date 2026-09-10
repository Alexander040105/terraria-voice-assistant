import { useEffect, useRef, useState } from 'react'
import { VoiceClient } from './ws-client'

const SAMPLE_RATE = 16000
const WINDOW_SIZE = 512
const SILENCE_SECONDS = 0.5

function App() {
  const [status, setStatus] = useState('idle')
  const [transcript, setTranscript] = useState('')
  const [answer, setAnswer] = useState('')
  const [isListening, setIsListening] = useState(false)
  const audioCtxRef = useRef(null)
  const workletNodeRef = useRef(null)
  const clientRef = useRef(null)

  useEffect(() => {
    const client = new VoiceClient()
    client.onStatus = (s) => setStatus(s)
    client.onTranscript = (t) => {
      setTranscript(t)
      setAnswer('')
    }
    client.onAnswer = (a) => setAnswer(a)
    client.onAudio = (buffer) => {
      const ctx = new AudioContext()
      ctx.decodeAudioData(buffer, (audio) => {
        const source = ctx.createBufferSource()
        source.buffer = audio
        source.connect(ctx.destination)
        source.start()
      })
    }
    client.connect()
    clientRef.current = client
    return () => client.close()
  }, [])

  const startListening = async () => {
    try {
      setTranscript('')
      setAnswer('')
      const audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE })
      audioCtxRef.current = audioCtx

      await audioCtx.audioWorklet.addModule('./audio/audio-processor.js')

      const mic = audioCtx.createMediaStreamSource(
        await navigator.mediaDevices.getUserMedia({ audio: true })
      )
      const node = new AudioWorkletNode(audioCtx, 'pcm-processor')

      node.port.onmessage = (e) => {
        clientRef.current?.sendPCM(e.data)
      }

      mic.connect(node)
      workletNodeRef.current = node
      setIsListening(true)
      setStatus('listening')
    } catch (err) {
      console.error(err)
      setStatus('mic-error')
    }
  }

  const stopListening = () => {
    const client = clientRef.current
    if (client) {
      // Feed silence so the backend VAD sees the end of speech.
      const silenceSamples = Math.floor(SILENCE_SECONDS * SAMPLE_RATE)
      const silence = new Int16Array(silenceSamples)
      for (let i = 0; i < silenceSamples; i += WINDOW_SIZE) {
        client.sendPCM(silence.subarray(i, i + WINDOW_SIZE).buffer)
      }
    }

    audioCtxRef.current?.close()
    workletNodeRef.current = null
    setIsListening(false)
    setStatus('idle')
  }

  return (
    <div style={{ padding: 20, fontFamily: 'sans-serif', maxWidth: 420, margin: '0 auto' }}>
      <h1 style={{ color: '#4caf50' }}>Terraria Voice Assistant</h1>
      <p>Status: <strong>{status}</strong></p>
      <button
        onClick={isListening ? stopListening : startListening}
        style={{
          padding: '12px 24px',
          fontSize: 16,
          borderRadius: 8,
          border: 'none',
          background: isListening ? '#f44336' : '#4caf50',
          color: 'white',
          cursor: 'pointer'
        }}
      >
        {isListening ? 'Stop' : 'Ask'}
      </button>
      <h3>Transcript</h3>
      <div style={{ minHeight: 24, padding: 8, background: '#f5f5f5', borderRadius: 4 }}>
        {transcript || '...'}
      </div>
      <h3>Answer</h3>
      <div style={{ minHeight: 48, padding: 8, background: '#f5f5f5', borderRadius: 4, whiteSpace: 'pre-wrap' }}>
        {answer || '...'}
      </div>
    </div>
  )
}

export default App
