import type {
  ApiError,
  CaptureHealth,
  CaptureInfo,
  JobSnapshot,
  ProbeConfig,
  ProbeSnapshot,
  RangeMode,
  RoiQuality,
  RoiRect,
  SessionResult,
  SessionSnapshot,
  WindowInfo,
} from '../types/api'

export class ApiClient {
  private token: string = ''

  constructor() {
    this.initToken()
  }

  public initToken(): string {
    if (typeof window === 'undefined') {
      return ''
    }
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ''))
    const tokenFromUrl = params.get('token')
    if (tokenFromUrl) {
      this.token = tokenFromUrl
      window.history.replaceState(
        { ...(window.history.state ?? {}), gcpToken: tokenFromUrl },
        '',
        `${window.location.pathname}${window.location.search}`,
      )
    } else if (typeof window.history.state?.gcpToken === 'string') {
      this.token = window.history.state.gcpToken
    }
    return this.token
  }

  public setToken(token: string) {
    this.token = token
  }

  public getToken(): string {
    return this.token
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers || {})
    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`)
    }
    if (!headers.has('Content-Type') && !(options.body instanceof FormData || options.body instanceof Blob)) {
      headers.set('Content-Type', 'application/json')
    }

    const method = options.method || 'GET'
    console.debug(`[API Request] ${method} ${path}`, options.body ?? '')
    const response = await fetch(path, {
      ...options,
      headers,
    })

    if (!response.ok) {
      let errData: ApiError = {
        code: `HTTP_${response.status}`,
        message: response.statusText,
      }
      try {
        const json = await response.json()
        if (json.error) {
          errData = json.error
        }
      } catch {
        // Fallback to status text
      }
      console.error(`[API Error] ${method} ${path} -> ${response.status}`, errData)
      throw errData
    }

    const data = await response.json()
    console.debug(`[API Response] ${method} ${path} ->`, data)
    return data
  }

  public async getHealth(): Promise<{ status: string; controller_ready: boolean; controller_enabled: boolean }> {
    return this.request('/api/health')
  }

  public async setControllerEnabled(enabled: boolean): Promise<{ enabled: boolean; available: boolean }> {
    return this.request('/api/controller', {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    })
  }

  public async wakeController(input: string): Promise<{ input: string; duration: string }> {
    return this.request('/api/controller/wake', {
      method: 'POST',
      body: JSON.stringify({ input }),
    })
  }

  public async quitApplication(): Promise<{ status: string }> {
    return this.request('/api/app/quit', { method: 'POST' })
  }

  public async getWindows(): Promise<WindowInfo[]> {
    const res = await this.request<{ windows: WindowInfo[] }>('/api/windows')
    return res.windows
  }

  public async attachCapture(windowId: number, backend: 'auto' | 'wgc' | 'dxcam' = 'auto', targetFps = 120): Promise<CaptureInfo> {
    const res = await this.request<{ capture: CaptureInfo }>('/api/capture/attach', {
      method: 'POST',
      body: JSON.stringify({
        window_id: windowId,
        backend,
        target_fps: targetFps,
      }),
    })
    return res.capture
  }

  public async getCaptureHealth(): Promise<CaptureHealth> {
    const res = await this.request<{ health: CaptureHealth }>('/api/capture/health')
    return res.health
  }

  public async getSession(): Promise<SessionSnapshot> {
    return this.request('/api/session')
  }

  public async updateConfig(changes: Partial<ProbeConfig>): Promise<SessionSnapshot> {
    return this.request('/api/session/config', {
      method: 'PUT',
      body: JSON.stringify(changes),
    })
  }

  public async updateRoi(roi: RoiRect): Promise<{ roi: RoiRect; quality: RoiQuality | null }> {
    return this.request('/api/session/roi', {
      method: 'POST',
      body: JSON.stringify(roi),
    })
  }

  public async startDeadzoneProbe(initialOutput = 0.0, step = 0.005): Promise<ProbeSnapshot> {
    const res = await this.request<{ probe: ProbeSnapshot }>('/api/deadzone/start', {
      method: 'POST',
      body: JSON.stringify({ initial_output: initialOutput, step, direction: 'x_positive' }),
    })
    return res.probe
  }

  public async updateDeadzoneProbe(output: number): Promise<ProbeSnapshot> {
    const res = await this.request<{ probe: ProbeSnapshot }>('/api/deadzone/update', {
      method: 'POST',
      body: JSON.stringify({ output }),
    })
    return res.probe
  }

  public async stopDeadzoneProbe(): Promise<ProbeSnapshot> {
    const res = await this.request<{ probe: ProbeSnapshot }>('/api/deadzone/stop', {
      method: 'POST',
    })
    return res.probe
  }

  public async startMeasurement(rangeMode?: RangeMode): Promise<JobSnapshot> {
    return this.request('/api/jobs/measurement', {
      method: 'POST',
      body: JSON.stringify({ range_mode: rangeMode }),
    })
  }

  public async startIdleNoise(): Promise<JobSnapshot> {
    return this.request('/api/jobs/idle-noise', {
      method: 'POST',
    })
  }

  public async getJob(jobId: string): Promise<JobSnapshot> {
    return this.request(`/api/jobs/${jobId}`)
  }

  public async cancelJob(jobId: string): Promise<JobSnapshot> {
    return this.request(`/api/jobs/${jobId}`, {
      method: 'DELETE',
    })
  }

  public async exportResult(format: 'json' | 'csv'): Promise<Blob> {
    const headers = new Headers()
    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`)
    }
    const res = await fetch(`/api/result/export?format=${format}`, { headers })
    if (!res.ok) {
      throw new Error(`Export failed: ${res.statusText}`)
    }
    return res.blob()
  }

  public async importResult(data: string | object): Promise<SessionResult> {
    const body = typeof data === 'string' ? data : JSON.stringify(data)
    const res = await this.request<{ result: SessionResult }>('/api/result/import', {
      method: 'POST',
      body,
    })
    return res.result
  }

  public async testAudio(soundType: 'start' | 'stop' | 'complete' | 'test' = 'test'): Promise<{ status: string; sound_type: string }> {
    return this.request('/api/audio/test', {
      method: 'POST',
      body: JSON.stringify({ sound_type: soundType }),
    })
  }
}

export const api = new ApiClient()
