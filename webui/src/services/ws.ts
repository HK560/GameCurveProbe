import { api } from './api'

export type EventHandler = (event: { seq: number; type: string; timestamp: string; payload: any; job_id?: string }) => void
export type PreviewHandler = (imageBlobUrl: string, meta: { width: number; height: number; frameId: number }) => void

class WebSocketManager {
  private eventsWs: WebSocket | null = null
  private previewWs: WebSocket | null = null
  private eventHandlers: Set<EventHandler> = new Set()
  private previewHandlers: Set<PreviewHandler> = new Set()
  private reconnectTimeout: any = null
  private reconnectDelay = 1000
  private isExplicitClose = false
  private currentPreviewUrl: string | null = null

  public connectEvents() {
    this.isExplicitClose = false
    const token = api.getToken()
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/ws/events?token=${token}`

    if (this.eventsWs) {
      this.eventsWs.close()
    }

    this.eventsWs = new WebSocket(wsUrl)

    this.eventsWs.onopen = () => {
      this.reconnectDelay = 1000
    }

    this.eventsWs.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data)
        for (const handler of this.eventHandlers) {
          handler(data)
        }
      } catch (err) {
        console.error('Error parsing WS message:', err)
      }
    }

    this.eventsWs.onclose = () => {
      if (!this.isExplicitClose) {
        this.scheduleReconnect()
      }
    }

    this.eventsWs.onerror = (err) => {
      console.warn('Events WS error:', err)
    }
  }

  public connectPreview() {
    const token = api.getToken()
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/ws/preview?token=${token}`

    if (this.previewWs) {
      this.previewWs.close()
    }

    this.previewWs = new WebSocket(wsUrl)
    this.previewWs.binaryType = 'arraybuffer'

    this.previewWs.onmessage = (msg) => {
      if (typeof msg.data === 'string') return
      const buffer = msg.data as ArrayBuffer
      if (buffer.byteLength < 20) return

      const view = new DataView(buffer)
      // Check magic "GCPV"
      const magic0 = view.getUint8(0)
      const magic1 = view.getUint8(1)
      const magic2 = view.getUint8(2)
      const magic3 = view.getUint8(3)
      if (magic0 !== 0x47 || magic1 !== 0x43 || magic2 !== 0x50 || magic3 !== 0x56) {
        return
      }

      const width = view.getUint16(4, true)
      const height = view.getUint16(6, true)
      const frameId = view.getUint32(8, true)

      const jpegBytes = buffer.slice(20)
      const blob = new Blob([jpegBytes], { type: 'image/jpeg' })

      if (this.currentPreviewUrl) {
        URL.revokeObjectURL(this.currentPreviewUrl)
      }
      this.currentPreviewUrl = URL.createObjectURL(blob)

      for (const handler of this.previewHandlers) {
        handler(this.currentPreviewUrl, { width, height, frameId })
      }
    }

    this.previewWs.onclose = () => {
      if (!this.isExplicitClose) {
        setTimeout(() => this.connectPreview(), 2000)
      }
    }
  }

  public onEvent(handler: EventHandler): () => void {
    this.eventHandlers.add(handler)
    return () => this.eventHandlers.delete(handler)
  }

  public onPreview(handler: PreviewHandler): () => void {
    this.previewHandlers.add(handler)
    return () => this.previewHandlers.delete(handler)
  }

  private scheduleReconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
    }
    this.reconnectTimeout = setTimeout(() => {
      this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 10000)
      this.connectEvents()
    }, this.reconnectDelay)
  }

  public close() {
    this.isExplicitClose = true
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
    }
    if (this.eventsWs) {
      this.eventsWs.close()
      this.eventsWs = null
    }
    if (this.previewWs) {
      this.previewWs.close()
      this.previewWs = null
    }
    if (this.currentPreviewUrl) {
      URL.revokeObjectURL(this.currentPreviewUrl)
      this.currentPreviewUrl = null
    }
  }
}

export const ws = new WebSocketManager()
