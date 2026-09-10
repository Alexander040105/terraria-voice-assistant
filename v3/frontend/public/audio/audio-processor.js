class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0][0]
    if (channel) {
      const int16 = new Int16Array(channel.length)
      for (let i = 0; i < channel.length; i++) {
        int16[i] = Math.max(-32768, Math.min(32767, channel[i] * 32768))
      }
      this.port.postMessage(int16.buffer, [int16.buffer])
    }
    return true
  }
}

registerProcessor('pcm-processor', PCMProcessor)
