export const TUTORIAL_COMPLETED_KEY = 'gamecurveprobe_tutorial_completed'

export type TutorialSource = 'first-run' | 'settings'
export type TutorialExit = 'completed' | 'skipped' | 'interrupted'

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>

export function hasCompletedTutorial(storage: StorageLike | undefined = globalThis.localStorage): boolean {
  try {
    return storage?.getItem(TUTORIAL_COMPLETED_KEY) === '1'
  } catch {
    return false
  }
}

export function markTutorialCompleted(storage: StorageLike | undefined = globalThis.localStorage): void {
  try {
    storage?.setItem(TUTORIAL_COMPLETED_KEY, '1')
  } catch {
    // Persistence is optional; the tutorial remains usable in restricted browsers.
  }
}

export function createTutorialState() {
  let value = {
    active: false,
    source: 'first-run' as TutorialSource,
    launchStep: 1,
    nodeIndex: 0,
  }

  return {
    snapshot: () => ({ ...value }),
    start(source: TutorialSource, launchStep: number) {
      value = { active: true, source, launchStep, nodeIndex: 0 }
    },
    goTo(nodeIndex: number) {
      value.nodeIndex = nodeIndex
    },
    stop(reason: TutorialExit) {
      const result = {
        restoreStep: value.source === 'first-run' ? 1 : value.launchStep,
        persistCompletion: reason === 'completed' || reason === 'skipped',
      }
      value.active = false
      return result
    },
  }
}
