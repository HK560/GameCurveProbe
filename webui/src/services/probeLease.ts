export interface ProbeLease {
  start(): void
  pause(): void
  dispose(): Promise<void>
}

export function createProbeLease(
  renew: () => Promise<unknown>,
  stop: () => Promise<unknown>,
): ProbeLease {
  let timer: ReturnType<typeof setInterval> | null = null

  function pause() {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  return {
    start() {
      pause()
      timer = setInterval(() => {
        void renew().catch(() => pause())
      }, 500)
    },
    pause,
    async dispose() {
      pause()
      await stop()
    },
  }
}
