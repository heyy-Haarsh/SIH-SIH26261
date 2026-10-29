/** Live mic → PCM 16 kHz → PRAMAN WebSocket proxy → Sarvam realtime STT. */

const TARGET_RATE = 16000

export interface LiveTranscriptHandlers {
  onPartial: (text: string) => void
  onFinal: (text: string) => void
  onError: (message: string) => void
  onStatus?: (message: string) => void
}

function downsampleTo16k(input: Float32Array, inputRate: number): Int16Array {
  if (inputRate === TARGET_RATE) {
    const out = new Int16Array(input.length)
    for (let i = 0; i < input.length; i += 1) {
      const s = Math.max(-1, Math.min(1, input[i]))
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }
    return out
  }
  const ratio = inputRate / TARGET_RATE
  const newLen = Math.max(1, Math.floor(input.length / ratio))
  const out = new Int16Array(newLen)
  for (let i = 0; i < newLen; i += 1) {
    const idx = Math.floor(i * ratio)
    const s = Math.max(-1, Math.min(1, input[idx] ?? 0))
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return out
}

function pcmToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength)
  let binary = ''
  const chunk = 0x8000
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk))
  }
  return btoa(binary)
}

function apiWsBase(): string {
  const http = import.meta.env.VITE_API_BASE_URL || `${window.location.protocol}//${window.location.host}/api/v1`
  if (http.startsWith('https://')) return http.replace(/^https/, 'wss')
  if (http.startsWith('http://')) return http.replace(/^http/, 'ws')
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${http.startsWith('/') ? http : `/${http}`}`
}

export async function startLiveDictation(
  role: string,
  handlers: LiveTranscriptHandlers,
): Promise<{ stop: () => Promise<void> }> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser cannot use the microphone. Type the note instead.')
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  })

  const { getDemoSession } = await import('@/lib/demoAuthSession')
  const session = getDemoSession()
  const userId = session.role === role ? session.userId : `demo-${role}`
  const qs = new URLSearchParams({ role, userId })
  const ws = new WebSocket(`${apiWsBase()}/scrutiny/transcribe/ws?${qs}`)
  ws.binaryType = 'arraybuffer'

  let audioCtx: AudioContext | null = null
  let processor: ScriptProcessorNode | null = null
  let source: MediaStreamAudioSourceNode | null = null
  let closed = false

  const cleanup = async () => {
    if (closed) return
    closed = true
    try {
      processor?.disconnect()
      source?.disconnect()
      await audioCtx?.close()
    } catch {
      /* ignore */
    }
    stream.getTracks().forEach((t) => t.stop())
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      try {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ event: 'flush' }))
          ws.send(JSON.stringify({ event: 'end' }))
        }
        ws.close(1000)
      } catch {
        /* ignore */
      }
    }
  }

  await new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error('Live speech session timed out.')), 15000)
    ws.onopen = () => {
      /* wait for proxy.ready */
    }
    ws.onerror = () => {
      window.clearTimeout(timer)
      reject(new Error('Could not connect to the speech service.'))
    }
    ws.onmessage = (ev) => {
      let msg: { event?: string; message?: string; text?: string; is_fatal?: boolean }
      try {
        msg = JSON.parse(String(ev.data))
      } catch {
        return
      }
      if (msg.event === 'proxy.ready' || msg.event === 'session.begin') {
        window.clearTimeout(timer)
        resolve()
        handlers.onStatus?.('Listening… text appears as you speak.')
        return
      }
      if (msg.event === 'error') {
        handlers.onError(msg.message || 'Speech service error.')
        if (msg.is_fatal) void cleanup()
        window.clearTimeout(timer)
        reject(new Error(msg.message || 'Speech service error.'))
      }
    }
  })

  // Keep listening after ready
  ws.onmessage = (ev) => {
    let msg: { event?: string; message?: string; text?: string; is_fatal?: boolean }
    try {
      msg = JSON.parse(String(ev.data))
    } catch {
      return
    }
    if (msg.event === 'transcript.partial' && msg.text) {
      handlers.onPartial(msg.text)
    } else if (msg.event === 'transcript.final' && msg.text) {
      handlers.onFinal(msg.text)
    } else if (msg.event === 'error') {
      handlers.onError(msg.message || 'Speech service error.')
      if (msg.is_fatal) void cleanup()
    }
  }
  ws.onclose = () => {
    if (!closed) void cleanup()
  }

  audioCtx = new AudioContext()
  // Some browsers start suspended until a gesture; Speak is already a click.
  if (audioCtx.state === 'suspended') await audioCtx.resume()
  source = audioCtx.createMediaStreamSource(stream)
  // ScriptProcessor is deprecated but widely available without a separate worklet file.
  processor = audioCtx.createScriptProcessor(4096, 1, 1)
  processor.onaudioprocess = (e) => {
    if (closed || ws.readyState !== WebSocket.OPEN) return
    const input = e.inputBuffer.getChannelData(0)
    const pcm = downsampleTo16k(input, audioCtx!.sampleRate)
    if (pcm.length === 0) return
    ws.send(JSON.stringify({ event: 'audio_input', audio: pcmToBase64(pcm) }))
  }
  const mute = audioCtx.createGain()
  mute.gain.value = 0
  source.connect(processor)
  processor.connect(mute)
  mute.connect(audioCtx.destination)

  return { stop: cleanup }
}
