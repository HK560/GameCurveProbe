import { driver, type Config } from 'driver.js'

interface DriverInstanceLike {
  drive: () => void
  destroy: () => void
}

type DriverFactory = (config: Config) => DriverInstanceLike

export function createTutorialDriver(factory: DriverFactory = driver) {
  let instance: DriverInstanceLike | null = null
  return {
    start(config: Config) {
      instance?.destroy()
      instance = factory(config)
      instance.drive()
    },
    destroy() {
      instance?.destroy()
      instance = null
    },
  }
}

interface WaitOptions {
  timeoutMs?: number
  pollMs?: number
  query?: (selector: string) => Element | null
  signal?: AbortSignal
}

export function waitForTourTarget(selector: string, options: WaitOptions = {}): Promise<boolean> {
  const timeoutMs = options.timeoutMs ?? 1500
  const pollMs = options.pollMs ?? 30
  const query = options.query ?? (value => document.querySelector(value))

  return new Promise(resolve => {
    const startedAt = Date.now()
    const check = () => {
      if (options.signal?.aborted) return resolve(false)
      if (query(selector)) return resolve(true)
      if (Date.now() - startedAt >= timeoutMs) return resolve(false)
      setTimeout(check, pollMs)
    }
    check()
  })
}
