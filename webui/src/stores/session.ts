import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../services/api'
import { ws } from '../services/ws'
import { t } from '../services/i18n'
import type {
  CaptureInfo,
  CaptureHealth,
  JobSnapshot,
  LogEntry,
  LogLevel,
  MeasurementPoint,
  ProbeConfig,
  ProbeSnapshot,
  RangeMode,
  RoiRect,
  SessionResult,
  SessionSnapshot,
  WindowInfo,
} from '../types/api'

export const STORAGE_CONFIG_KEY = 'gamecurveprobe_config'

export function getLocalConfig(): Partial<ProbeConfig> | null {
  if (typeof localStorage === 'undefined' || !localStorage.getItem) return null
  try {
    const raw = localStorage.getItem(STORAGE_CONFIG_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (err) {
    console.warn('Failed to read config from localStorage:', err)
    return null
  }
}

export function saveLocalConfig(config: Partial<ProbeConfig>) {
  if (typeof localStorage === 'undefined' || !localStorage.setItem) return
  try {
    const existing = getLocalConfig() || {}
    const merged = { ...existing, ...config }
    localStorage.setItem(STORAGE_CONFIG_KEY, JSON.stringify(merged))
  } catch (err) {
    console.warn('Failed to save config to localStorage:', err)
  }
}

export const useSessionStore = defineStore('session', () => {
  const session = ref<SessionSnapshot | null>(null)
  const localConfig = ref<Partial<ProbeConfig> | null>(getLocalConfig())
  const windows = ref<WindowInfo[]>([])
  const probe = ref<ProbeSnapshot | null>(null)
  const activeStep = ref<number>(1)
  const isAttaching = ref<boolean>(false)
  const isUpdatingConfig = ref<boolean>(false)
  const livePreviewUrl = ref<string | null>(null)
  const livePreviewMeta = ref<{ width: number; height: number; frameId: number } | null>(null)
  const measurementLogs = ref<LogEntry[]>([])
  const livePoints = ref<MeasurementPoint[]>([])

  const internalActiveJob = ref<JobSnapshot | null>(null)
  const internalLastJob = ref<JobSnapshot | null>(null)
  const internalLastResult = ref<SessionResult | null>(null)
  const importedResult = ref<SessionResult | null>(null)
  const internalCapture = ref<CaptureInfo | null>(null)
  const captureHealth = ref<CaptureHealth | null>(null)
  const internalNoise = ref<SessionSnapshot['noise']>(null)

  const activeJob = computed(() => internalActiveJob.value ?? session.value?.active_job ?? null)
  const lastJob = computed(() => internalLastJob.value ?? session.value?.last_job ?? null)
  const lastResult = computed(() => internalLastResult.value ?? session.value?.last_result ?? null)
  const capture = computed(() => internalCapture.value ?? session.value?.capture ?? null)
  const config = computed(() => {
    const backendConfig = session.value?.config
    const local = localConfig.value
    if (backendConfig && local) {
      return { ...backendConfig, ...local }
    }
    return backendConfig ?? (local as ProbeConfig | null) ?? null
  })
  const roi = computed(() => session.value?.roi ?? null)
  const roiQuality = computed(() => session.value?.roi_quality ?? null)
  const noise = computed(() => internalNoise.value ?? session.value?.noise ?? null)

  async function loadInitialData() {
    try {
      session.value = await api.getSession()
      if (session.value) {
        internalCapture.value = session.value.capture ?? null
        internalActiveJob.value = session.value.active_job ?? null
        internalLastJob.value = session.value.last_job ?? null
        internalLastResult.value = session.value.last_result ?? null
        internalNoise.value = session.value.noise ?? null
      }
    } catch (err) {
      console.warn('Failed to load session:', err)
    }

    // Auto-restore saved user preferences from local storage
    const saved = getLocalConfig()
    if (saved && Object.keys(saved).length > 0) {
      localConfig.value = saved
      if (session.value?.config) {
        session.value.config = { ...session.value.config, ...saved }
      }
      try {
        const synced = await api.updateConfig(saved)
        if (synced) {
          session.value = synced
        }
      } catch {
        // Backend offline or standalone mode, local config remains active
      }
    }

    await fetchWindows()
  }

  async function fetchWindows() {
    try {
      windows.value = await api.getWindows()
    } catch (err) {
      console.warn('Failed to fetch windows:', err)
    }
  }

  async function attachCapture(windowId: number, backend: 'auto' | 'wgc' | 'dxcam' = 'auto', targetFps = 120) {
    isAttaching.value = true
    try {
      const cap = await api.attachCapture(windowId, backend, targetFps)
      internalCapture.value = cap
      if (session.value) {
        session.value.capture = cap
      }
      try {
        captureHealth.value = await api.getCaptureHealth()
      } catch {
        captureHealth.value = null
      }
      return cap
    } finally {
      isAttaching.value = false
    }
  }

  async function refreshCaptureHealth() {
    captureHealth.value = await api.getCaptureHealth()
    return captureHealth.value
  }

  async function updateConfig(changes: Partial<ProbeConfig>) {
    isUpdatingConfig.value = true
    try {
      saveLocalConfig(changes)
      localConfig.value = getLocalConfig()
      try {
        session.value = await api.updateConfig(changes)
      } catch (err) {
        if (session.value?.config) {
          session.value.config = { ...session.value.config, ...changes }
        }
      }
      return session.value
    } finally {
      isUpdatingConfig.value = false
    }
  }

  async function updateRoi(newRoi: RoiRect) {
    const res = await api.updateRoi(newRoi)
    if (session.value) {
      session.value.roi = res.roi
      session.value.roi_quality = res.quality
    }
    return res
  }

  async function startDeadzoneProbe(initialOutput = 0.0, step = 0.005) {
    probe.value = await api.startDeadzoneProbe(initialOutput, step)
    return probe.value
  }

  async function updateDeadzoneProbe(output: number) {
    probe.value = await api.updateDeadzoneProbe(output)
    return probe.value
  }

  async function stopDeadzoneProbe() {
    probe.value = await api.stopDeadzoneProbe()
    return probe.value
  }

  function addLog(level: LogLevel, message: string) {
    const now = new Date()
    const timestamp = [
      now.getHours().toString().padStart(2, '0'),
      now.getMinutes().toString().padStart(2, '0'),
      now.getSeconds().toString().padStart(2, '0'),
    ].join(':')
    measurementLogs.value.push({
      id: Math.random().toString(36).slice(2, 9),
      timestamp,
      level,
      message,
    })
    if (measurementLogs.value.length > 500) {
      measurementLogs.value.shift()
    }
  }

  function clearLogs() {
    measurementLogs.value = []
  }

  async function startMeasurement(rangeMode?: RangeMode) {
    livePoints.value = []
    addLog('action', t('log_starting_measurement'))
    const job = await api.startMeasurement(rangeMode)
    internalActiveJob.value = job
    if (session.value) {
      session.value.active_job = job
    }
    return job
  }

  async function startIdleNoise() {
    const job = await api.startIdleNoise()
    internalActiveJob.value = job
    if (session.value) {
      session.value.active_job = job
    }
    return job
  }

  async function cancelJob(jobId: string) {
    addLog('action', t('log_canceling_measurement'))
    const job = await api.cancelJob(jobId)
    if (internalActiveJob.value?.id === jobId) {
      internalActiveJob.value = job
    }
    return job
  }

  function handleWsEvent(event: { type: string; payload: any; job_id?: string }) {
    if (event.type === 'session_sync' && event.payload?.session) {
      session.value = event.payload.session
      if (event.payload.session.capture) {
        internalCapture.value = event.payload.session.capture
      }
      internalActiveJob.value = event.payload.session.active_job ?? null
      internalLastJob.value = event.payload.session.last_job ?? null
      internalLastResult.value = event.payload.session.last_result ?? null
      internalNoise.value = event.payload.session.noise ?? null
    } else if (event.type === 'job_status' && event.payload?.job) {
      internalActiveJob.value = event.payload.job
      if (session.value) {
        session.value.active_job = event.payload.job
      }
      if (event.payload.job.state === 'running' && event.payload.job.kind === 'measurement') {
        livePoints.value = []
      }
    } else if (event.type === 'job_progress' && event.payload?.data) {
      const data = event.payload.data
      if (internalActiveJob.value) {
        internalActiveJob.value.progress = data
      }
      if (session.value?.active_job) {
        session.value.active_job.progress = data
      }
      if (data.phase) {
        if (data.phase === 'stage_start') {
          addLog('info', data.message || `${t('log_probe_started')}: ${t('total_points_count')} ${data.total_points} ${t('points_suffix')}`)
        } else if (data.phase === 'point_settle') {
          addLog('settle', data.message || `[${data.current_point}/${data.total_points}] ${t('log_point_settle')}`)
        } else if (data.phase === 'point_sampling') {
          addLog('sampling', data.message || `[${data.current_point}/${data.total_points}] ${t('log_point_sampling')}`)
        } else if (data.phase === 'point_retry') {
          addLog('warn', data.message || `[${data.current_point}/${data.total_points}] ${t('log_point_retry')}`)
        } else if (data.phase === 'point_done') {
          addLog('success', data.message || `[${data.current_point}/${data.total_points}] ${t('log_point_done')}`)
          if (data.point) {
            livePoints.value.push(data.point)
          }
        } else if (data.phase === 'stage_completed') {
          addLog('info', data.message || t('log_stage_completed'))
        }
      } else if (data.message) {
        addLog('info', data.message)
      }
    } else if (event.type === 'job_completed') {
      internalLastJob.value = event.payload.job
      internalActiveJob.value = null
      if (session.value) {
        session.value.last_job = event.payload.job
        session.value.active_job = null
      }
      if (event.payload.result && event.payload.job?.kind === 'measurement') {
        internalLastResult.value = event.payload.result
        if (session.value) {
          session.value.last_result = event.payload.result
        }
        addLog('success', t('log_measurement_success'))
      } else if (event.payload.result && event.payload.job?.kind === 'idle_noise') {
        internalNoise.value = event.payload.result
        if (session.value) {
          session.value.noise = event.payload.result
        }
      }
    } else if (event.type === 'job_failed' || event.type === 'job_canceled') {
      internalLastJob.value = event.payload.job
      internalActiveJob.value = null
      if (session.value) {
        session.value.last_job = event.payload.job
        session.value.active_job = null
      }
      if (event.type === 'job_canceled') {
        addLog('warn', t('log_measurement_canceled'))
      } else {
        addLog('error', `${t('log_task_failed')}: ${event.payload?.error || t('unknown_error')}`)
      }
    } else if (event.type === 'capture_changed' && event.payload?.capture) {
      internalCapture.value = event.payload.capture
      if (session.value) {
        session.value.capture = event.payload.capture
      }
    } else if (event.type === 'roi_changed') {
      if (session.value) {
        session.value.roi = event.payload.roi
        session.value.roi_quality = event.payload.quality
      }
    } else if (event.type === 'config_updated' && event.payload?.config) {
      if (session.value) {
        session.value.config = event.payload.config
      }
    } else if (event.type === 'deadzone_probe_updated' && event.payload?.probe) {
      probe.value = event.payload.probe
    } else if (event.type === 'result_imported' && event.payload?.result) {
      importedResult.value = event.payload.result
    }
  }

  function loadSimulatedResult(data: SessionResult) {
    internalLastResult.value = data
    importedResult.value = data
    if (session.value) {
      session.value.last_result = data
      if (data.config) {
        session.value.config = { ...session.value.config, ...data.config }
      }
    } else {
      session.value = {
        id: 'simulated-session',
        config: data.config ? (data.config as any) : { inner_deadzone: 0.0, outer_deadzone: 1.0 },
        last_result: data,
      } as any
    }
  }

  function initListeners() {
    ws.onEvent((ev) => handleWsEvent(ev))
    ws.onPreview((url, meta) => {
      livePreviewUrl.value = url
      livePreviewMeta.value = meta
    })
  }

  return {
    session,
    windows,
    probe,
    activeStep,
    isAttaching,
    isUpdatingConfig,
    livePreviewUrl,
    livePreviewMeta,
    measurementLogs,
    livePoints,
    activeJob,
    lastJob,
    lastResult,
    importedResult,
    capture,
    captureHealth,
    config,
    roi,
    roiQuality,
    noise,
    addLog,
    clearLogs,
    loadInitialData,
    fetchWindows,
    attachCapture,
    refreshCaptureHealth,
    updateConfig,
    updateRoi,
    startDeadzoneProbe,
    updateDeadzoneProbe,
    stopDeadzoneProbe,
    startMeasurement,
    startIdleNoise,
    cancelJob,
    loadSimulatedResult,
    handleWsEvent,
    initListeners,
  }
})
