import React, { useState, useEffect, useRef } from 'react'
import { io } from 'socket.io-client'
import { 
  ArrowUp, BookOpen, MessageSquare, Upload, X, FileText, 
  Mic, MicOff, Volume2, Settings,   History, Trash2, Plus, 
  Server, VolumeX, Brain, Search, Cpu, Globe
} from 'lucide-react'
import ChatMessageContent from './ChatMessageContent.jsx'

const getBackendHost = () => {
  return localStorage.getItem('pirandello_backend_host') || `${window.location.hostname}:8000`
}
const getApiBase = () => `http://${getBackendHost()}`
const socket = io(`http://${getBackendHost()}`, { autoConnect: true })

function SettingToggle({ checked, onChange, label, description, icon: Icon }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      className={`w-full flex items-center gap-4 p-4 rounded-2xl border transition-all duration-300 text-left ${
        checked
          ? 'bg-amber-600/10 border-amber-500/30 shadow-md shadow-amber-500/5'
          : 'bg-white/[0.02] border-white/5 hover:border-white/10 hover:bg-white/[0.04]'
      }`}
    >
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
        checked ? 'bg-amber-500/20 text-amber-200' : 'bg-white/5 text-white/30'
      }`}>
        <Icon size={20} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-white">{label}</div>
        {description && <div className="text-[11px] text-white/35 mt-0.5 leading-snug">{description}</div>}
      </div>
      <div className={`relative w-12 h-7 rounded-full shrink-0 transition-colors duration-300 ${
        checked ? 'bg-amber-500' : 'bg-white/10'
      }`}>
        <span className={`absolute top-1 left-1 w-5 h-5 rounded-full bg-white shadow-md transition-transform duration-300 ${
          checked ? 'translate-x-5' : 'translate-x-0'
        }`} />
      </div>
    </button>
  )
}

const sessionStorageKey = (m) => `pirandello_session_${m}`

function App() {
  const [mode, setMode] = useState(() => {
    return localStorage.getItem('pirandello_last_mode') || 'pirandello'
  })
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [sessions, setSessions] = useState([])
  const [showSettings, setShowSettings] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [historySearch, setHistorySearch] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [uploadedFile, setUploadedFile] = useState(null)
  
  const [playingMsgIndex, setPlayingMsgIndex] = useState(null)
  const [autoplay, setAutoplay] = useState(() => {
    return localStorage.getItem('pirandello_autoplay') === 'true'
  })
  const autoplayRef = useRef(autoplay)
  const gateResponseRef = useRef(false)
  const [tempHost, setTempHost] = useState(() => getBackendHost())
  const [providers, setProviders] = useState({})
  const [activeProvider, setActiveProvider] = useState('lm_studio')
  const [providerConfigOpen, setProviderConfigOpen] = useState(null)
  const [providerConfigs, setProviderConfigs] = useState({})
  const [memories, setMemories] = useState([])
  const [expandedMemoryKey, setExpandedMemoryKey] = useState(null)
  const isCreatingSessionRef = useRef(false)
  const modeRef = useRef(mode)

  useEffect(() => {
    autoplayRef.current = autoplay
  }, [autoplay])

  useEffect(() => {
    modeRef.current = mode
    localStorage.setItem('pirandello_last_mode', mode)
  }, [mode])

  const fetchSessions = async (forMode = modeRef.current, searchQ = historySearch) => {
    try {
      const params = new URLSearchParams({ mode: forMode })
      const q = (searchQ || '').trim()
      if (q) params.set('q', q)
      const res = await fetch(`${getApiBase()}/api/sessions?${params}`)
      const data = await res.json()
      if (forMode === modeRef.current) {
        setSessions(data.sessions || [])
      }
    } catch (e) {
      console.error('fetchSessions:', e)
    }
  }

  const fetchMessages = async (id) => {
    if (!id) return
    try {
      const res = await fetch(`${getApiBase()}/api/sessions/${id}/messages`)
      const data = await res.json()
      const formatted = (data.messages || []).map(m => ({
        role: m.role,
        content: m.content,
        done: true
      }))
      setMessages(formatted)
    } catch (e) {
      console.error('fetchMessages:', e)
    }
  }

  const fetchMemories = async () => {
    try {
      const res = await fetch(`${getApiBase()}/api/memories`)
      const data = await res.json()
      setMemories(data.memories || [])
    } catch (e) {
      console.error('fetchMemories:', e)
    }
  }

  const fetchProviders = async () => {
    try {
      const res = await fetch(`${getApiBase()}/api/providers`)
      const data = await res.json()
      setProviders(data.providers || {})
      setActiveProvider(data.active || 'lm_studio')
      const configs = {}
      Object.entries(data.providers || {}).forEach(([name, p]) => {
        configs[name] = { api_url: p.api_url || '', model: p.model || '', api_key: p.api_key || '' }
      })
      setProviderConfigs(configs)
    } catch (e) {
      console.error('fetchProviders:', e)
    }
  }

  const handleActivateProvider = async (name) => {
    try {
      const res = await fetch(`${getApiBase()}/api/providers/activate?name=${encodeURIComponent(name)}`, { method: 'POST' })
      if (res.ok) {
        setActiveProvider(name)
        localStorage.setItem('pirandello_active_provider', name)
      }
    } catch (e) {
      console.error('handleActivateProvider:', e)
    }
  }

  const handleUpdateProviderConfig = async (name) => {
    const cfg = providerConfigs[name]
    if (!cfg) return
    try {
      await fetch(`${getApiBase()}/api/providers/config?name=${encodeURIComponent(name)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cfg),
      })
      await fetchProviders()
    } catch (e) {
      console.error('handleUpdateProviderConfig:', e)
    }
  }

  const handleToggleAutoplay = () => {
    const newValue = !autoplay
    setAutoplay(newValue)
    localStorage.setItem('pirandello_autoplay', newValue ? 'true' : 'false')
  }

  const handleSaveHost = () => {
    localStorage.setItem('pirandello_backend_host', tempHost.trim())
    window.location.reload()
  }
  
  const endRef = useRef(null)
  const fileRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  
  const audioPlayerRef = useRef(null)
  const audioObjectUrlRef = useRef(null)
  const audioPrimedRef = useRef(false)
  const ttsInFlightRef = useRef(false)
  const pendingAudioUrlRef = useRef(null)
  const lastTtsAudioUrlRef = useRef(null)
  const playAudioFromUrlRef = useRef(null)
  const sessionIdRef = useRef(sessionId)
  const [autoplayBlocked, setAutoplayBlocked] = useState(false)

  useEffect(() => {
    const player = new Audio()
    player.preload = 'auto'
    audioPlayerRef.current = player
    return () => {
      player.pause()
      revokeAudioObjectUrl()
      audioPlayerRef.current = null
    }
  }, [])

  const revokeAudioObjectUrl = () => {
    if (audioObjectUrlRef.current) {
      URL.revokeObjectURL(audioObjectUrlRef.current)
      audioObjectUrlRef.current = null
    }
  }

  /** Sblocca l'autoplay sul click Invio (il browser richiede un play() nel gesto utente). */
  const primeAudioPlayback = () => {
    const player = audioPlayerRef.current
    if (!player || audioPrimedRef.current) return
    player.src =
      'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA='
    player.volume = 0.001
    player
      .play()
      .then(() => {
        player.pause()
        player.removeAttribute('src')
        player.load()
        audioPrimedRef.current = true
        setAutoplayBlocked(false)
      })
      .catch(() => {})
  }

  const buildAudioSrc = (pathOrUrl) => {
    const base = pathOrUrl.startsWith('http') ? pathOrUrl : `${getApiBase()}${pathOrUrl}`
    const sep = base.includes('?') ? '&' : '?'
    return `${base}${sep}t=${Date.now()}`
  }

  const playAudioFromUrl = async (pathOrUrl, msgIndex = null) => {
    if (!pathOrUrl) return
    const player = audioPlayerRef.current
    if (!player) return

    const src = buildAudioSrc(pathOrUrl)
    try {
      revokeAudioObjectUrl()
      player.pause()
      player.volume = 1
      if (msgIndex !== null) setPlayingMsgIndex(msgIndex)

      await new Promise((resolve, reject) => {
        let settled = false
        const finish = (fn) => {
          if (settled) return
          settled = true
          clearTimeout(timer)
          player.removeEventListener('canplaythrough', onReady)
          player.removeEventListener('loadeddata', onReady)
          player.removeEventListener('error', onErr)
          fn()
        }
        const onReady = () => finish(resolve)
        const onErr = () => finish(() => reject(new Error('Caricamento audio fallito')))
        const timer = setTimeout(() => finish(resolve), 10000)

        player.onended = () => setPlayingMsgIndex(null)
        player.addEventListener('canplaythrough', onReady)
        player.addEventListener('loadeddata', onReady)
        player.addEventListener('error', onErr)
        player.src = src
        player.load()
      })

      await player.play()
      setAutoplayBlocked(false)
      pendingAudioUrlRef.current = null
    } catch (err) {
      const blocked =
        err?.name === 'NotAllowedError' ||
        (err?.message && /not allowed|user didn't interact/i.test(err.message))
      if (blocked) {
        pendingAudioUrlRef.current = pathOrUrl
        setAutoplayBlocked(true)
        console.warn('Autoplay bloccato dal browser — clicca Ascolta sulla risposta')
      } else {
        console.error('Audio play failed:', err)
      }
      setPlayingMsgIndex(null)
    }
  }

  playAudioFromUrlRef.current = playAudioFromUrl

  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  useEffect(() => {
    fetchSessions(mode)
  }, [mode])

  // Sync active provider from backend on mount
  useEffect(() => {
    ;(async () => {
      try {
        const res = await fetch(`${getApiBase()}/api/providers`)
        if (res.ok) {
          const data = await res.json()
          setActiveProvider(data.active || 'lm_studio')
          localStorage.setItem('pirandello_active_provider', data.active || 'lm_studio')
        }
      } catch (_) {}
    })()
  }, [])

  useEffect(() => {
    if (sessionId) {
      if (isCreatingSessionRef.current) {
        isCreatingSessionRef.current = false
        return
      }
      fetchMessages(sessionId)
    } else {
      setMessages([])
    }
  }, [sessionId])

  // --- WebSocket Setup ---
  useEffect(() => {
    const syncOnConnect = () => {
      fetchSessions(modeRef.current)
    }

    fetchSessions(modeRef.current)

    socket.on('connect', syncOnConnect)

    socket.on('sessions_list', (data) => {
      setSessions(data.sessions || [])
    })

    socket.on('session_updated', (data) => {
      if (!data?.id) return
      setSessions((prev) =>
        prev.map((s) =>
          s.id === data.id ? { ...s, title: data.title || s.title } : s
        )
      )
    })

    socket.on('session_created', (data) => {
      isCreatingSessionRef.current = true
      if (sessionIdRef.current !== data.id) {
        setSessionId(data.id)
      }
      fetchSessions()
    })

    socket.on('session_deleted', (data) => {
      if (sessionIdRef.current === data.session_id) {
        setSessionId(null)
        setMessages([])
      }
      fetchSessions()
    })

    socket.on('all_data_cleared', (data) => {
      if (data?.hard_reset) {
        setSessionId(null)
        setMessages([])
        setSessions([])
        setMemories([])
        localStorage.removeItem(sessionStorageKey('pirandello'))
        localStorage.removeItem(sessionStorageKey('wiki'))
        return
      }
      const clearedMode = data?.mode
      if (clearedMode && clearedMode !== modeRef.current) return
      setSessionId(null)
      setMessages([])
      setSessions([])
    })

    socket.on('memory_updated', () => {
      fetchMemories()
    })

    socket.on('chat_history', (data) => {
      if (data.session_id === sessionIdRef.current) {
        const formatted = (data.messages || []).map(m => ({
          role: m.role,
          content: m.content,
          done: true
        }))
        setMessages(formatted)
      }
    })

    if (socket.connected) {
      syncOnConnect()
    }

    socket.on('assistant_preparing', (data) => {
      if (data.session_id !== sessionIdRef.current) return
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: '', done: false, preparing: true },
      ])
    })

    socket.on('assistant_ready', (data) => {
      if (data.session_id !== sessionIdRef.current) return
      gateResponseRef.current = false
      setIsStreaming(false)
      ttsInFlightRef.current = false
      const text = data.text ?? ''
      const audioUrl = data.audio_url || null
      if (data.tts_error) {
        console.error('TTS Error:', data.tts_error)
      }
      setMessages(prev => {
        const prepIdx = prev.findIndex(m => m.preparing)
        const msg = {
          role: 'assistant',
          content: text,
          done: true,
          preparing: false,
          audioUrl,
        }
        if (prepIdx >= 0) {
          const next = [...prev]
          next[prepIdx] = msg
          return next
        }
        return [...prev, msg]
      })
      if (audioUrl && autoplayRef.current && playAudioFromUrlRef.current) {
        playAudioFromUrlRef.current(audioUrl)
      }
      fetchSessions()
      fetchMemories()
    })

    socket.on('token', (data) => {
      if (gateResponseRef.current) return
      if (data.session_id !== sessionIdRef.current) return
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last && last.role === 'assistant' && !last.done) {
          const updated = [...prev]
          updated[updated.length - 1] = { ...last, content: last.content + data.token }
          return updated
        }
        return [...prev, { role: 'assistant', content: data.token, done: false }]
      })
    })

    socket.on('done', (data) => {
      setIsStreaming(false)

      if (data.session_id !== sessionIdRef.current) {
        fetchSessions()
        return
      }

      if (data.gated) {
        return
      }

      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last && last.role === 'assistant') {
          const updated = [...prev]
          updated[updated.length - 1] = { ...last, done: true }
          return updated
        }
        return prev
      })

      fetchSessions()
      fetchMemories()
    })

    socket.on('tts_ready', (data) => {
      ttsInFlightRef.current = false
      if (!data?.url) return
      lastTtsAudioUrlRef.current = data.url
      setMessages((prev) => {
        const next = [...prev]
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].role === 'assistant') {
            next[i] = { ...next[i], audioUrl: data.url }
            break
          }
        }
        return next
      })
      if (playAudioFromUrlRef.current) {
        playAudioFromUrlRef.current(data.url)
      }
    })

    socket.on('tts_error', (data) => {
      ttsInFlightRef.current = false
      console.error('TTS Error:', data.error)
      setPlayingMsgIndex(null)
    })

    socket.on('upload_result', (data) => {
      if (data.success) {
        setMessages(prev => [...prev, {
          role: 'system',
          content: `Documento aggiunto con successo alla Wiki: **${data.filename}**`
        }])
      } else {
        alert('Errore caricamento: ' + data.error)
      }
      setUploadedFile(null)
    })

    return () => {
      socket.off('connect'); socket.off('session_ready'); socket.off('sessions_list')
      socket.off('session_created'); socket.off('session_updated'); socket.off('session_deleted'); socket.off('all_data_cleared'); socket.off('memory_updated')
      socket.off('chat_history'); socket.off('token'); socket.off('done')
      socket.off('assistant_preparing'); socket.off('assistant_ready')
      socket.off('tts_ready'); socket.off('tts_error'); socket.off('upload_result')
    }
  }, [])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  // --- Actions ---
  const handleSend = () => {
    const text = input.trim()
    if (!text || isStreaming) return

    ttsInFlightRef.current = false
    if (autoplayRef.current) {
      primeAudioPlayback()
    }

    let activeSession = sessionId
    if (!activeSession) {
      const newUuid = crypto.randomUUID()
      activeSession = newUuid
      isCreatingSessionRef.current = true
      setSessionId(newUuid)
      socket.emit('create_session', {
        session_id: newUuid,
        title: text,
        mode,
      })
    }

    setMessages(prev => [...prev, { role: 'user', content: text, done: true }])
    setIsStreaming(true)
    gateResponseRef.current = mode === 'pirandello' && autoplayRef.current
    socket.emit('chat_message', {
      message: text,
      session_id: activeSession,
      mode: mode,
      history: [],
      autovoice: mode === 'pirandello' && autoplayRef.current,
      provider: activeProvider,
    })
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleNewChat = () => {
    isCreatingSessionRef.current = false
    setSessionId(null)
    setMessages([])
    setShowHistory(false)
  }

  const handleSelectSession = (id) => {
    isCreatingSessionRef.current = false
    setSessionId(id)
    fetchMessages(id)
    socket.emit('get_session_messages', { session_id: id })
    setShowHistory(false)
  }

  const handleDeleteSession = async (e, id) => {
    e.stopPropagation()
    if (!window.confirm('Eliminare questa conversazione? L\'operazione non si può annullare.')) {
      return
    }
    setSessions((prev) => prev.filter((s) => s.id !== id))
    if (sessionIdRef.current === id) {
      setSessionId(null)
      setMessages([])
    }
    try {
      await fetch(`${getApiBase()}/api/sessions/${encodeURIComponent(id)}`, {
        method: 'DELETE',
      })
    } catch (err) {
      console.error('delete session HTTP:', err)
      fetchSessions(mode)
    }
    if (socket.connected) {
      socket.emit('delete_session', { session_id: id })
    }
  }

  const handleHardReset = async () => {
    if (
      !window.confirm(
        'RESET: verranno eliminate TUTTE le chat (Pirandello e Wiki) e tutta la memoria salvata. Operazione irreversibile. Procedere?'
      )
    ) {
      return
    }
    setSessionId(null)
    setMessages([])
    setSessions([])
    setMemories([])
    localStorage.removeItem(sessionStorageKey('pirandello'))
    localStorage.removeItem(sessionStorageKey('wiki'))
    setShowSettings(false)
    setShowHistory(false)
    try {
      await fetch(`${getApiBase()}/api/sessions?hard_reset=true`, { method: 'DELETE' })
    } catch (e) {
      console.error('hard reset HTTP:', e)
    }
    if (socket.connected) {
      socket.emit('clear_all_data', { hard_reset: true })
    }
  }

  const handleOpenHistory = () => {
    fetchSessions(mode, historySearch)
    setShowHistory(true)
  }

  useEffect(() => {
    if (!showHistory) return
    const t = setTimeout(() => fetchSessions(modeRef.current, historySearch), 280)
    return () => clearTimeout(t)
  }, [showHistory, historySearch, mode])

  const handleOpenSettings = () => {
    setTempHost(getBackendHost())
    fetchMemories()
    fetchProviders()
    setShowSettings(true)
  }

  const handleDeleteMemory = async (category, key) => {
    if (!window.confirm('Eliminare questo ricordo dalla memoria?')) return
    try {
      await fetch(`${getApiBase()}/api/memories?category=${encodeURIComponent(category)}&key=${encodeURIComponent(key)}`, {
        method: 'DELETE'
      })
      fetchMemories()
    } catch (e) {
      console.error(e)
    }
  }

  const handleModeSwitch = (newMode) => {
    if (newMode === mode) return
    setIsStreaming(false)
    stopAudio()
    isCreatingSessionRef.current = false
    setHistorySearch('')
    setMode(newMode)
    setSessionId(null)
    setMessages([])
  }

  // --- Voice Recording ---
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      mediaRecorderRef.current = mr
      audioChunksRef.current = []
      mr.ondataavailable = (e) => audioChunksRef.current.push(e.data)
      mr.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/wav' })
        const file = new File([blob], `voice_${Date.now()}.wav`, { type: 'audio/wav' })
        uploadFile(file)
        stream.getTracks().forEach(t => t.stop())
      }
      mr.start()
      setIsRecording(true)
    } catch { alert('Microfono non disponibile') }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    setIsRecording(false)
  }

  // --- File Upload ---
  const uploadFile = (file) => {
    const reader = new FileReader()
    reader.onload = () => {
      const base64 = reader.result.split(',')[1]
      socket.emit('upload_file', { filename: file.name, file: base64 })
    }
    reader.readAsDataURL(file)
  }

  const handleFilePick = (e) => {
    const f = e.target.files?.[0]
    if (f) { setUploadedFile(f); uploadFile(f) }
  }

  // Drag and Drop (wiki mode only)
  const onDragOver = (e) => {
    e.preventDefault()
    if (mode === 'wiki') setIsDragging(true)
  }

  const onDragLeave = () => {
    setIsDragging(false)
  }

  const onDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    if (mode !== 'wiki') return
    const file = e.dataTransfer.files[0]
    if (file) {
      setUploadedFile(file)
      uploadFile(file)
    }
  }

  // --- TTS Synthesis ---
  const playTtsForMessage = (message, index) => {
    if (playingMsgIndex === index) {
      stopAudio()
      return
    }
    primeAudioPlayback()
    setPlayingMsgIndex(index)
    const cachedUrl =
      messages[index]?.audioUrl || pendingAudioUrlRef.current || lastTtsAudioUrlRef.current
    if (cachedUrl) {
      playAudioFromUrl(cachedUrl, index)
      return
    }
    if (ttsInFlightRef.current) return
    ttsInFlightRef.current = true
    socket.emit('request_tts', {
      message: message,
      session_id: sessionIdRef.current,
    })
  }

  const stopAudio = () => {
    const player = audioPlayerRef.current
    if (player) {
      player.pause()
      player.removeAttribute('src')
      player.load()
    }
    revokeAudioObjectUrl()
    setPlayingMsgIndex(null)
  }

  return (
    <div 
      className={`h-screen w-full flex flex-col relative overflow-hidden bg-mesh transition-all duration-700 ${mode === 'pirandello' ? 'mode-pirandello' : 'mode-wiki'} ${isDragging ? 'scale-[0.99]' : ''}`}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {/* Aurora Layer */}
      <div className="absolute inset-0 bg-mesh-gradient opacity-30 pointer-events-none"></div>

      {/* Header */}
      <header className="relative z-20 flex items-center justify-between px-6 py-4 glass border-b border-white/5">
        
        {/* Navigation Buttons in the top-left */}
        <div className="flex items-center gap-3">
          <img src="/favicon.png" className="w-7 h-7 rounded-lg opacity-80" alt="" />
          <div className="flex glass rounded-full p-1 border border-white/5">
          <button
            onClick={() => handleModeSwitch('pirandello')}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold uppercase tracking-wider transition-all duration-300 ${
              mode === 'pirandello'
                ? 'bg-amber-600/30 text-amber-200 shadow-lg border border-amber-500/20'
                : 'text-white/40 hover:text-white/70 border border-transparent'
            }`}
          >
            <MessageSquare size={13} />
            Pirandello
          </button>
          <button
            onClick={() => handleModeSwitch('wiki')}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold uppercase tracking-wider transition-all duration-300 ${
              mode === 'wiki'
                ? 'bg-emerald-600/30 text-emerald-200 shadow-lg border border-emerald-500/20'
                : 'text-white/40 hover:text-white/70 border border-transparent'
            }`}
          >
            <BookOpen size={13} />
            Wiki
          </button>
        </div>
        </div>

        {/* Right side drawers toggles */}
        <div className="flex items-center gap-2.5">
          <button 
            onClick={handleOpenHistory}
            className="flex items-center justify-center w-9 h-9 rounded-full glass border border-white/5 text-white/50 hover:text-white hover:bg-white/5 transition-all duration-300"
            title={mode === 'wiki' ? 'Cronologia Wiki' : 'Cronologia Pirandello'}
          >
            <History size={16} />
          </button>
          <button 
            onClick={handleOpenSettings}
            className="flex items-center justify-center w-9 h-9 rounded-full glass border border-white/5 text-white/50 hover:text-white hover:bg-white/5 transition-all duration-300"
            title="Impostazioni"
          >
            <Settings size={16} />
          </button>
        </div>
      </header>

      {/* Sessions History Drawer (Left Slide) */}
      <aside className={`fixed inset-y-0 left-0 z-50 w-80 bg-surface-container/95 backdrop-blur-2xl border-r border-white/5 transform transition-transform duration-500 ease-out flex flex-col p-6 ${showHistory ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-sm font-bold uppercase tracking-[0.2em] text-white/70 flex items-center gap-2">
            <History size={15} className={mode === 'wiki' ? 'text-emerald-300' : 'text-amber-300'} />
            {mode === 'wiki' ? 'Cronologia Wiki' : 'Cronologia Pirandello'}
          </h2>
          <button onClick={() => setShowHistory(false)} className="p-1.5 hover:bg-white/5 rounded-full text-white/40 hover:text-white"><X size={18}/></button>
        </div>

        <button 
          onClick={handleNewChat}
          className={`w-full flex items-center justify-center gap-2 p-3.5 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/5 text-xs font-bold uppercase tracking-wider transition-all duration-300 mb-4 ${
            mode === 'wiki' ? 'text-emerald-200' : 'text-amber-200'
          }`}
        >
          <Plus size={16} /> Nuova Conversazione
        </button>

        <div className="relative mb-4">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/25 pointer-events-none" />
          <input
            type="search"
            value={historySearch}
            onChange={(e) => setHistorySearch(e.target.value)}
            placeholder="Cerca per titolo o testo..."
            className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-white/5 border border-white/5 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-white/15"
          />
        </div>

        <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 custom-scrollbar">
          {sessions.map(s => (
            <div
              key={s.id}
              onClick={() => handleSelectSession(s.id)}
              className={`group w-full text-left p-4 rounded-xl transition-all duration-300 border cursor-pointer flex items-center justify-between ${
                sessionId === s.id
                  ? mode === 'wiki'
                    ? 'bg-emerald-600/10 border-emerald-500/30 text-white shadow-md shadow-emerald-500/5'
                    : 'bg-amber-600/10 border-amber-500/30 text-white shadow-md shadow-amber-500/5'
                  : 'border-transparent text-white/50 hover:bg-white/5 hover:text-white'
              }`}
            >
              <div className="overflow-hidden pr-2 flex-1 min-w-0">
                <div className="text-xs font-bold truncate">{s.title || "Nuova Conversazione"}</div>
                <div className="text-[9px] opacity-35 mt-1">{new Date(s.created_at).toLocaleDateString('it-IT')}</div>
              </div>
              <button
                type="button"
                onClick={(e) => handleDeleteSession(e, s.id)}
                className={`shrink-0 flex items-center gap-1 px-2 py-1.5 rounded-lg border text-[10px] font-bold uppercase tracking-wider transition-all ${
                  mode === 'wiki'
                    ? 'border-red-500/25 text-red-300/80 hover:bg-red-500/15 hover:text-red-200 hover:border-red-500/40'
                    : 'border-red-500/25 text-red-300/80 hover:bg-red-500/15 hover:text-red-200 hover:border-red-500/40'
                }`}
                title="Elimina questa chat"
                aria-label="Elimina chat"
              >
                <Trash2 size={12} />
                <span>Elimina</span>
              </button>
            </div>
          ))}
          {sessions.length === 0 && (
            <div className="text-center py-20 opacity-20 text-[11px] italic">
              {historySearch.trim()
                ? 'Nessun risultato per la ricerca'
                : mode === 'wiki'
                  ? 'Nessuna conversazione Wiki salvata'
                  : 'Nessuna conversazione Pirandello salvata'}
            </div>
          )}
        </div>
      </aside>

      {/* Settings Drawer (Right Slide) */}
      <aside className={`fixed inset-y-0 right-0 z-50 w-[min(100vw,22rem)] sm:w-96 bg-[#0c0e14]/98 backdrop-blur-2xl border-l border-white/10 shadow-2xl transform transition-transform duration-500 ease-out flex flex-col p-5 sm:p-6 ${showSettings ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-[0.2em] text-white/70">Impostazioni</h2>
            <p className="text-[10px] text-amber-200/50 uppercase tracking-widest mt-1">Preferenze</p>
          </div>
          <button onClick={() => setShowSettings(false)} className="p-1.5 hover:bg-white/5 rounded-full text-white/40 hover:text-white"><X size={18}/></button>
        </div>

        <div className="space-y-8 flex-1 overflow-y-auto pr-1 custom-scrollbar">
          <section className="space-y-3">
            <h3 className="text-[10px] uppercase tracking-[0.25em] text-white/30 font-bold">Voce</h3>
            <SettingToggle
              checked={autoplay}
              onChange={handleToggleAutoplay}
              label="Autoplay risposte"
              description="Ascolta automaticamente le risposte con la voce Giuseppe (italiano)"
              icon={autoplay ? Volume2 : VolumeX}
            />
          </section>

          <section className="space-y-3">
            <h3 className="text-[10px] uppercase tracking-[0.25em] text-white/30 font-bold flex items-center gap-2">
              <Cpu size={12} className="text-amber-300/80" /> Provider
            </h3>
            <div className="rounded-2xl border border-white/8 bg-black/25 overflow-hidden">
              {Object.keys(providers).length === 0 ? (
                <div className="text-center py-6 px-4 text-[11px] text-white/25 italic">
                  Carica provider dal backend...
                </div>
              ) : (
                <div className="divide-y divide-white/5">
                  {Object.entries(providers).map(([name, p]) => {
                    const isActive = activeProvider === name
                    const isOpen = providerConfigOpen === name
                    return (
                      <div key={name} className="p-3">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
                            isActive ? 'bg-amber-500/20 text-amber-200' : 'bg-white/5 text-white/30'
                          }`}>
                            {p.category === 'local' ? <Server size={14} /> : <Globe size={14} />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-semibold text-white">{p.display_name || name}</span>
                              {p.category === 'local' ? (
                                <span className="text-[8px] uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-white/5 text-white/30">Locale</span>
                              ) : (
                                <span className="text-[8px] uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-300/60">Cloud</span>
                              )}
                            </div>
                            <div className="text-[10px] text-white/35 mt-0.5 truncate">{p.model || 'Modello predefinito'}</div>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleActivateProvider(name)}
                            className={`px-3 py-1.5 rounded-full text-[9px] font-bold uppercase tracking-wider border transition-all shrink-0 ${
                              isActive
                                ? 'bg-amber-500/20 border-amber-500/40 text-amber-200 shadow-sm shadow-amber-500/10'
                                : 'border-white/10 text-white/30 hover:text-white/60 hover:border-white/20'
                            }`}
                          >
                            {isActive ? 'Attivo' : 'Attiva'}
                          </button>
                          <button
                            type="button"
                            onClick={() => setProviderConfigOpen(isOpen ? null : name)}
                            className="p-1.5 text-white/25 hover:text-white/60 hover:bg-white/5 rounded-lg transition-all"
                          >
                            <Settings size={13} />
                          </button>
                        </div>

                        {/* Config expand */}
                        {isOpen && (
                          <div className="mt-3 pt-3 border-t border-white/5 space-y-2.5">
                            <div>
                              <label className="text-[9px] uppercase tracking-wider text-white/30 block mb-1">API URL</label>
                              <input
                                type="text"
                                value={providerConfigs[name]?.api_url || p.api_url || ''}
                                onChange={(e) => setProviderConfigs(prev => ({
                                  ...prev,
                                  [name]: { ...prev[name], api_url: e.target.value }
                                }))}
                                className="w-full px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-xs text-white placeholder-white/20 outline-none focus:border-amber-400/40"
                                placeholder={p.api_url || 'URL del provider...'}
                              />
                            </div>
                            <div>
                              <label className="text-[9px] uppercase tracking-wider text-white/30 block mb-1">Modello</label>
                              <input
                                type="text"
                                value={providerConfigs[name]?.model || p.model || ''}
                                onChange={(e) => setProviderConfigs(prev => ({
                                  ...prev,
                                  [name]: { ...prev[name], model: e.target.value }
                                }))}
                                className="w-full px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-xs text-white placeholder-white/20 outline-none focus:border-amber-400/40"
                                placeholder={p.model || 'Nome modello...'}
                              />
                            </div>
                            {p.category === 'cloud' && (
                              <div>
                                <label className="text-[9px] uppercase tracking-wider text-white/30 block mb-1">API Key</label>
                                <input
                                  type="password"
                                  value={providerConfigs[name]?.api_key || ''}
                                  onChange={(e) => setProviderConfigs(prev => ({
                                    ...prev,
                                    [name]: { ...prev[name], api_key: e.target.value }
                                  }))}
                                  className="w-full px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-xs text-white placeholder-white/20 outline-none focus:border-amber-400/40"
                                  placeholder="Inserisci API key..."
                                />
                              </div>
                            )}
                            <button
                              type="button"
                              onClick={() => handleUpdateProviderConfig(name)}
                              className="w-full py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white text-[10px] font-bold uppercase tracking-wider border border-white/5 transition-all"
                            >
                              Salva configurazione
                            </button>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-[10px] uppercase tracking-[0.25em] text-white/30 font-bold">Connessione</h3>
            <div className="p-4 rounded-2xl glass border border-white/5 space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center text-amber-200/70">
                  <Server size={18} />
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">Server backend</div>
                  <div className="text-[11px] text-white/35">host:porta del servizio Python</div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {['localhost:8000', `${window.location.hostname}:8000`].filter((v, i, a) => a.indexOf(v) === i).map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => setTempHost(preset)}
                    className={`px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider border transition-all ${
                      tempHost === preset
                        ? 'bg-amber-600/20 border-amber-500/40 text-amber-200'
                        : 'border-white/10 text-white/40 hover:text-white/70 hover:border-white/20'
                    }`}
                  >
                    {preset}
                  </button>
                ))}
              </div>
              <input
                type="text"
                value={tempHost}
                onChange={(e) => setTempHost(e.target.value)}
                placeholder="localhost:8000"
                className="w-full px-4 py-3 rounded-xl bg-black/40 border border-white/15 text-sm text-white placeholder-white/25 outline-none focus:border-amber-400/60 focus:ring-2 focus:ring-amber-500/25 transition-all"
              />
              <button
                type="button"
                onClick={handleSaveHost}
                className="w-full py-3.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-black text-xs font-bold uppercase tracking-wider transition-all shadow-lg shadow-amber-500/25 border border-amber-300/50"
              >
                Applica e ricarica
              </button>
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-[10px] uppercase tracking-[0.25em] text-white/30 font-bold flex items-center gap-2">
                <Brain size={12} className="text-amber-300/80" /> Memoria
              </h3>
              {memories.length > 0 && (
                <span className="text-[10px] font-bold text-amber-200/70 tabular-nums">{memories.length}</span>
              )}
            </div>
            <p className="text-[11px] text-white/40 leading-relaxed">
              Fatti ricordati su di te (nome, preferenze). Si aggiornano quando ti presenti o quando Pirandello li salva.
            </p>
            <div className="rounded-2xl border border-white/8 bg-black/25 overflow-hidden">
              {memories.length === 0 ? (
                <div className="text-center py-10 px-4 text-[11px] text-white/25 italic">
                  Nessun ricordo ancora — presentati in chat (es. «mi chiamo …»)
                </div>
              ) : (
                <ul className="max-h-56 sm:max-h-72 overflow-y-auto custom-scrollbar divide-y divide-white/5">
                  {memories.map((m) => {
                    const id = `${m.category}-${m.key}`
                    const expanded = expandedMemoryKey === id
                    const long = (m.value?.length || 0) > 72
                    return (
                      <li key={id} className="p-3 hover:bg-white/[0.03] transition-colors">
                        <div className="flex items-start gap-2">
                          <button
                            type="button"
                            className="min-w-0 flex-1 text-left"
                            onClick={() => long && setExpandedMemoryKey(expanded ? null : id)}
                            disabled={!long}
                          >
                            <div className="text-[10px] uppercase tracking-wider text-amber-200/60 font-bold">{m.category}</div>
                            <div className={`text-xs text-white/85 mt-1 ${expanded ? '' : 'line-clamp-2'}`}>
                              <span className="text-white/45">{m.key}: </span>
                              {m.value}
                            </div>
                            {long && (
                              <span className="text-[10px] text-amber-200/50 mt-1 inline-block">
                                {expanded ? 'Comprimi' : 'Mostra tutto'}
                              </span>
                            )}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteMemory(m.category, m.key)}
                            className="p-2 text-white/25 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all shrink-0"
                            title="Elimina ricordo"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </section>
        </div>

        <div className="pt-6 border-t border-white/5 space-y-2">
          <p className="text-[10px] text-white/30 leading-relaxed px-1">
            Elimina tutte le chat Pirandello e Wiki, più i ricordi in memoria e il file memory.md.
          </p>
          <button 
            onClick={handleHardReset} 
            className="w-full flex items-center justify-center gap-2 py-4 rounded-2xl bg-red-500/10 hover:bg-red-500 text-red-400 hover:text-white border border-red-500/20 font-bold text-xs uppercase tracking-wider transition-all duration-300"
          >
            <Trash2 size={15} /> Reset
          </button>
        </div>
      </aside>

      {/* Close sidebar overlays when active */}
      {(showHistory || showSettings) && (
        <div 
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity duration-300"
          onClick={() => { setShowHistory(false); setShowSettings(false); }}
        />
      )}

      {/* Messages Feed */}
      <main className="flex-1 overflow-y-auto px-4 py-8 relative z-10">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
              <div className="text-6xl mb-6 opacity-10 select-none">&#9670;</div>
              {mode === 'pirandello' ? (
                <div>
                  <p className="text-2xl mb-2 opacity-50 font-light" style={{ fontFamily: 'var(--font-headline)', fontStyle: 'italic' }}>
                    "Parlatemi... Io vi risponderò."
                  </p>
                  <p className="text-xs opacity-25 max-w-sm mx-auto leading-relaxed">
                    Dialogate con Luigi Pirandello. Interrogatelo sulla filosofia delle sue opere, le maschere sociali e la scomposizione della personalità.
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <p className="text-2xl mb-2 opacity-50 font-light" style={{ fontFamily: 'var(--font-headline)' }}>
                    Gestione Archivi Wiki
                  </p>
                  <p className="text-xs opacity-25 max-w-sm mx-auto leading-relaxed">
                    Caricate file di testo o dettate note. Il bibliotecario analizzerà e organizzerà automaticamente le pagine enciclopediche e i concetti.
                  </p>
                  <button
                    onClick={() => fileRef.current?.click()}
                    className="mt-6 inline-flex items-center gap-2 px-6 py-3.5 rounded-2xl bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-200 border border-emerald-500/20 text-xs font-bold uppercase tracking-wider transition-all duration-300 shadow-lg shadow-emerald-500/5 active:scale-95 cursor-pointer"
                  >
                    <Upload size={14} className="text-emerald-300" />
                    Carica Documento
                  </button>
                </div>
              )}
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} msg-in`}>
              <div className={`max-w-[85%] px-5 py-3.5 rounded-2xl leading-relaxed text-[13.5px] border ${
                m.role === 'user'
                  ? 'glass-light text-white rounded-br-md border-white/10'
                  : m.role === 'system'
                  ? 'glass border border-emerald-500/20 text-emerald-300/80 text-[11px] rounded-bl-md shadow-lg shadow-emerald-500/5'
                  : 'glass text-white/90 rounded-bl-md border-white/5 shadow-2xl'
              }`}>
                {m.role === 'user' && (
                  <span className="whitespace-pre-wrap">{m.content}</span>
                )}
                {m.role === 'system' && (
                  <ChatMessageContent content={m.content} accent="emerald" />
                )}
                {m.role === 'assistant' && m.done && (
                  <ChatMessageContent
                    content={m.content}
                    accent={mode === 'wiki' ? 'emerald' : 'amber'}
                  />
                )}
                {m.role === 'assistant' && !m.done && m.preparing && (
                  <span className="italic text-white/45 text-sm">
                    Sta preparando la risposta…
                  </span>
                )}
                {m.role === 'assistant' && !m.done && !m.preparing && (
                  <>
                    <span className="whitespace-pre-wrap">{m.content}</span>
                    <span className="inline-flex ml-1.5 gap-0.5 align-middle">
                      <span className="w-1.5 h-1.5 bg-white/40 rounded-full dot-pulse" />
                      <span className="w-1.5 h-1.5 bg-white/40 rounded-full dot-pulse" style={{ animationDelay: '0.2s' }} />
                      <span className="w-1.5 h-1.5 bg-white/40 rounded-full dot-pulse" style={{ animationDelay: '0.4s' }} />
                    </span>
                  </>
                )}
                {m.role === 'assistant' && m.done && mode === 'pirandello' && (
                  <button
                    onClick={() => playTtsForMessage(m.content, i)}
                    className={`inline-flex items-center justify-center p-1.5 ml-2.5 rounded-full border align-middle transition-all duration-300 ${
                      playingMsgIndex === i
                        ? 'text-amber-300 border-amber-500/40 bg-amber-500/20 shadow-md shadow-amber-500/10'
                        : 'text-white/20 border-white/5 hover:text-white/60 hover:bg-white/5'
                    }`}
                    title={playingMsgIndex === i ? "Interrompi voce" : "Ascolta voce"}
                  >
                    <Volume2 size={12} className={playingMsgIndex === i ? 'animate-pulse' : ''} />
                  </button>
                )}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </main>

      {/* Input controls layout */}
      <div className="relative z-20 px-4 pb-6 pt-4 bg-gradient-to-t from-background via-background/90 to-transparent">
        <div className="max-w-3xl mx-auto">
          {uploadedFile && (
            <div className="mb-3 flex items-center gap-3 glass rounded-2xl px-4 py-3 text-xs text-white/50 border border-white/5 animate-fade-in-up">
              <FileText size={14} className="text-emerald-400" />
              <span className="truncate flex-1">{uploadedFile.name}</span>
              <span className="text-[9px] text-emerald-400/80 font-bold uppercase tracking-wider animate-pulse">Caricamento...</span>
            </div>
          )}

          {autoplayBlocked && mode === 'pirandello' && (
            <div className="mb-3 flex items-center justify-between gap-3 rounded-2xl px-4 py-3 border border-amber-500/30 bg-amber-500/10 text-xs text-amber-100">
              <span>Il browser ha bloccato l&apos;audio automatico.</span>
              <button
                type="button"
                onClick={() => {
                  primeAudioPlayback()
                  if (pendingAudioUrlRef.current) {
                    playAudioFromUrl(pendingAudioUrlRef.current)
                  }
                }}
                className="shrink-0 px-3 py-1.5 rounded-lg bg-amber-500/25 hover:bg-amber-500/40 font-bold uppercase tracking-wider text-[10px]"
              >
                Ascolta ora
              </button>
            </div>
          )}

          <div className="flex items-center gap-2.5 glass rounded-2xl px-4 py-2 border border-white/5 focus-within:ring-1 focus-within:ring-white/10 transition-all duration-500 shadow-2xl">
            {/* Upload button — always visible */}
            <button
              onClick={() => fileRef.current?.click()}
              className={`p-2.5 rounded-xl transition-all duration-300 mb-1 ${mode === 'wiki' ? 'text-emerald-400/70 hover:text-emerald-300 hover:bg-emerald-500/10' : 'text-white/20 hover:text-white/50 hover:bg-white/5'}`}
              title={mode === 'wiki' ? "Seleziona file da archiviare" : "Allega file"}
            >
              <Upload size={17} />
            </button>
            <input ref={fileRef} type="file" className="hidden" onChange={handleFilePick} accept=".txt,.md" />

            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={mode === 'pirandello' ? "Esprimi un pensiero a Pirandello..." : "Ordina al bibliotecario di catalogare o cercare..."}
              className="flex-1 bg-transparent text-white placeholder-white/10 outline-none resize-none py-3 px-1 text-sm max-h-32 leading-relaxed custom-scrollbar"
              rows={1}
              disabled={isStreaming}
            />
            <button
              onClick={isRecording ? stopRecording : startRecording}
              className={`p-2.5 rounded-xl transition-all duration-300 mb-1 ${isRecording ? 'text-red-400 bg-red-500/10 animate-pulse' : 'text-white/20 hover:text-white hover:bg-white/5'}`}
              title={isRecording ? "Ferma registrazione" : "Dettatura vocale"}
            >
              {isRecording ? <MicOff size={17} /> : <Mic size={17} />}
            </button>
            <button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              className="p-3 rounded-xl bg-white/5 text-white/30 disabled:opacity-10 hover:bg-white/10 hover:text-white transition-all duration-300 mb-1 border border-white/5 shadow-inner"
            >
              <ArrowUp size={16} strokeWidth={2.5} />
            </button>
          </div>
        </div>
      </div>

      {/* Drag Over blurred visual overlay (Wiki Mode only) */}
      {isDragging && (
        <div className="fixed inset-0 z-50 border-[6px] border-dashed border-emerald-500/35 bg-black/75 backdrop-blur-md flex flex-col items-center justify-center animate-fade-in text-center p-8 pointer-events-none">
          <div className="w-20 h-20 bg-emerald-500/10 text-emerald-300 rounded-full flex items-center justify-center mb-6 border border-emerald-500/30 shadow-[0_0_30px_rgba(16,185,129,0.1)]">
            <Upload size={32} className="animate-bounce" />
          </div>
          <h3 className="text-xl font-bold text-white uppercase tracking-wider">Aggiungi agli Archivi Wiki</h3>
          <p className="text-xs text-white/40 max-w-sm mt-2 leading-relaxed">
            Rilascia qui il file (.txt, .md) per caricarlo automaticamente e indicizzarlo nella Wiki.
          </p>
        </div>
      )}
    </div>
  )
}

export default App
