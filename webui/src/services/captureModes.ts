import { t } from './i18n'

export type CaptureMode = 'auto' | 'wgc' | 'dxcam'

export interface CaptureModeInfo {
  label: string
  occlusionSafe: boolean
  warning: string | null
}

export function captureModeInfo(mode: CaptureMode): CaptureModeInfo {
  const modes: Record<CaptureMode, CaptureModeInfo> = {
    auto: {
      label: t('wgc_desc'),
      occlusionSafe: true,
      warning: null,
    },
    wgc: {
      label: 'Windows Graphics Capture (WGC)',
      occlusionSafe: true,
      warning: null,
    },
    dxcam: {
      label: t('dxcam_desc'),
      occlusionSafe: false,
      warning: t('dxcam_warning'),
    },
  }
  return modes[mode]
}

export function captureErrorMessage(error: { code?: string; message?: string }): string {
  const messagesMap: Record<string, string> = {
    WINDOW_MINIMIZED: t('err_window_minimized'),
    WINDOW_GONE: t('err_window_gone'),
    ROI_INVALIDATED: t('err_roi_invalidated'),
    CAPTURE_STALLED: t('err_capture_stalled'),
    CAPTURE_BLACK_FRAME: t('err_capture_black_frame'),
  }
  return (error.code && messagesMap[error.code]) || error.message || t('err_capture_failed')
}
