export type CaptureMode = 'auto' | 'wgc' | 'dxcam'

export interface CaptureModeInfo {
  label: string
  occlusionSafe: boolean
  warning: string | null
}

const modes: Record<CaptureMode, CaptureModeInfo> = {
  auto: {
    label: 'Auto（WGC 独立窗口捕获）',
    occlusionSafe: true,
    warning: null,
  },
  wgc: {
    label: 'Windows Graphics Capture（WGC）',
    occlusionSafe: true,
    warning: null,
  },
  dxcam: {
    label: '屏幕区域兼容模式（DXGI）',
    occlusionSafe: false,
    warning: '屏幕区域兼容模式，窗口被遮挡时会捕获遮挡内容。',
  },
}

export function captureModeInfo(mode: CaptureMode): CaptureModeInfo {
  return modes[mode]
}

export function captureErrorMessage(error: { code?: string; message?: string }): string {
  const messages: Record<string, string> = {
    WINDOW_MINIMIZED: '目标窗口已最小化，请不要最小化窗口。',
    WINDOW_GONE: '目标窗口已关闭，请重新选择窗口。',
    ROI_INVALIDATED: '捕获画面尺寸已变化，请重新选择 ROI。',
    CAPTURE_STALLED: '窗口捕获已停止出帧，请重新绑定窗口。',
    CAPTURE_BLACK_FRAME: '窗口持续返回黑画面，可能不支持 WGC 捕获。',
  }
  return (error.code && messages[error.code]) || error.message || '抓取窗口失败'
}
