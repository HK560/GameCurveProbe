export const VIGEM_WARNING_DISMISSED_KEY = 'gamecurveprobe_vigembus_warning_dismissed'

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>

export function shouldShowVigemWarning(
  healthCheckSucceeded: boolean,
  controllerReady: boolean,
  storage: StorageLike | undefined = globalThis.localStorage,
): boolean {
  if (!healthCheckSucceeded || controllerReady) return false
  try {
    return storage?.getItem(VIGEM_WARNING_DISMISSED_KEY) !== '1'
  } catch {
    return true
  }
}

export function dismissVigemWarning(storage: StorageLike | undefined = globalThis.localStorage): void {
  try {
    storage?.setItem(VIGEM_WARNING_DISMISSED_KEY, '1')
  } catch {
    // The warning remains dismissible for this session when storage is unavailable.
  }
}
