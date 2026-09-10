export class VoiceClient {
  ws = null
  onTranscript = () => {}
  onAnswer = () => {}
  onAudio = () => {}
  onStatus = () => {}

  connect(url = 'ws://localhost:8000/ws/voice') {
    this.ws = new WebSocket(url)
    this.ws.binaryType = 'arraybuffer'

    this.ws.onopen = () => this.onStatus('connected')
    this.ws.onclose = () => this.onStatus('disconnected')
    this.ws.onerror = () => this.onStatus('error')

    this.ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        const msg = JSON.parse(event.data)
        if (msg.transcript) this.onTranscript(msg.transcript)
        if (msg.answer) this.onAnswer(msg.answer)
      } else {
        this.onAudio(event.data)
      }
    }
  }

  sendPCM(buffer) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(buffer)
    }
  }

  close() {
    this.ws?.close()
  }
}
