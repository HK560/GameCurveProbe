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

class ApiClient {
  private token: string = ''

  constructor() {
    this.initToken()
  }

  public initToken(): string {
    if (typeof window === 'undefined') {
      return ''
    }
    const params = new URLSearchParams(window.location.search)
    const tokenFromUrl = params.get('token')
    if (tokenFromUrl) {
      this.token = tokenFromUrl
      localStorage.setItem('gcp_token', tokenFromUrl)
    } else {
      this.token = localStorage.getItem('gcp_token') || ''
    }
    return this.token
  }

  public setToken(token: string) {
    this.token = token
    if (typeof window !== 'undefined') {
      localStorage.setItem('gcp_token', token)
    }
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
      throw errData
    }

    return response.json()
  }

  public async getHealth(): Promise<{ status: string; controller_ready: boolean }> {
    return this.request('/api/health')
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
}

export const api = new ApiClient()
