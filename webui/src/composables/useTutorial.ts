import { inject, provide, readonly, ref, type InjectionKey } from 'vue'
import { createTutorialDemo } from '../services/tutorialDemo'
import type { TutorialAction } from '../services/tutorialSteps'
import { createTutorialState, markTutorialCompleted, type TutorialExit, type TutorialSource } from '../services/tutorialState'

interface TutorialPageAdapter {
  getPage: () => number
  setPage: (page: number) => void
}

export type TutorialPhase = TutorialAction | 'idle'

export function shouldDisposeRealProbe(tutorialActive: boolean, probeActive: boolean): boolean {
  return !tutorialActive && probeActive
}

export function createTutorialController(pages: TutorialPageAdapter) {
  const state = createTutorialState()
  const active = ref(false)
  const source = ref<TutorialSource>('first-run')
  const nodeIndex = ref(0)
  const phase = ref<TutorialPhase>('idle')
  const demo = createTutorialDemo()

  function start(nextSource: TutorialSource) {
    if (active.value) stop('interrupted')
    state.start(nextSource, pages.getPage())
    source.value = nextSource
    nodeIndex.value = 0
    phase.value = 'idle'
    active.value = true
  }

  function stop(reason: TutorialExit) {
    if (!active.value) return
    const result = state.stop(reason)
    active.value = false
    phase.value = 'idle'
    pages.setPage(result.restoreStep)
    if (result.persistCompletion) markTutorialCompleted()
  }

  function goTo(index: number) {
    state.goTo(index)
    nodeIndex.value = index
  }

  function applyAction(action?: TutorialAction) {
    phase.value = action ?? 'idle'
  }

  function display<T extends { capture: unknown; lastResult: unknown }>(real: T) {
    if (!active.value) return real
    return { ...real, capture: demo.capture, lastResult: demo.result }
  }

  async function guardAction<T>(action: () => T | Promise<T>): Promise<T | undefined> {
    if (active.value) return undefined
    return await action()
  }

  return {
    active: readonly(active),
    source: readonly(source),
    nodeIndex: readonly(nodeIndex),
    phase: readonly(phase),
    demo,
    start,
    stop,
    goTo,
    applyAction,
    setPage: pages.setPage,
    display,
    guardAction,
  }
}

export type TutorialController = ReturnType<typeof createTutorialController>
const tutorialKey: InjectionKey<TutorialController> = Symbol('gamecurveprobe-tutorial')

export function provideTutorial(controller: TutorialController) {
  provide(tutorialKey, controller)
  return controller
}

export function useTutorial(): TutorialController {
  const controller = inject(tutorialKey)
  if (!controller) throw new Error('Tutorial controller has not been provided')
  return controller
}
