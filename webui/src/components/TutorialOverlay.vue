<script setup lang="ts">
import { nextTick, onBeforeUnmount, watch } from 'vue'
import { driver, type Driver } from 'driver.js'
import { useTutorial } from '../composables/useTutorial'
import { currentLocale } from '../services/i18n'
import { createTutorialSteps, type TutorialStepDefinition } from '../services/tutorialSteps'
import { waitForTourTarget } from '../services/tutorialDriver'

const tutorial = useTutorial()
let driverInstance: Driver | null = null
let abortController: AbortController | null = null
let closing = false

const labels = () => currentLocale.value === 'zh'
  ? { next: '下一步', previous: '上一步', done: '完成', close: '跳过教程', progress: '第 {{current}} / {{total}} 项' }
  : { next: 'Next', previous: 'Previous', done: 'Finish', close: 'Skip tutorial', progress: '{{current}} of {{total}}' }

async function prepareStep(step: TutorialStepDefinition) {
  tutorial.applyAction(step.action)
  if (step.page) {
    tutorial.setPage(step.page)
    await nextTick()
  }
  if (!step.element) return true
  const ready = await waitForTourTarget(step.element, { signal: abortController?.signal })
  if (!ready) console.warn(`[tutorial] target unavailable: ${step.id} (${step.element})`)
  return ready
}

async function move(offset: 1 | -1) {
  const instance = driverInstance
  if (!instance) return
  const current = instance.getActiveIndex() ?? 0
  const steps = createTutorialSteps(currentLocale.value)
  const nextIndex = current + offset
  if (nextIndex >= steps.length) {
    finish('completed')
    return
  }
  if (nextIndex < 0) return
  tutorial.goTo(nextIndex)
  await prepareStep(steps[nextIndex])
  if (driverInstance !== instance || abortController?.signal.aborted) return
  instance.moveTo(nextIndex)
}

function finish(reason: 'completed' | 'skipped' | 'interrupted') {
  if (closing) return
  closing = true
  abortController?.abort()
  const instance = driverInstance
  driverInstance = null
  instance?.destroy()
  tutorial.stop(reason)
  closing = false
}

async function launch(startIndex = 0) {
  abortController?.abort()
  abortController = new AbortController()
  driverInstance?.destroy()
  const steps = createTutorialSteps(currentLocale.value)
  const text = labels()
  await prepareStep(steps[startIndex])
  if (!tutorial.active.value || abortController.signal.aborted) return

  driverInstance = driver({
    steps: steps.map((step, index) => ({
      element: step.element,
      waitForElement: 1500,
      skipMissingElement: true,
      disableActiveInteraction: true,
      popover: {
        title: `<span class="tutorial-chapter">${currentLocale.value === 'zh' ? `第 ${step.chapter}/7 章` : `Chapter ${step.chapter}/7`}</span>${step.title}`,
        description: step.description,
        onNextClick: () => void move(1),
        onPrevClick: () => void move(-1),
        onCloseClick: () => finish('skipped'),
        onDoneClick: () => finish('completed'),
      },
      data: { id: step.id, index },
    })),
    animate: true,
    smoothScroll: true,
    allowClose: false,
    allowKeyboardControl: true,
    stagePadding: 8,
    stageRadius: 10,
    popoverOffset: 14,
    popoverClass: 'gamecurveprobe-tutorial',
    showProgress: true,
    progressText: text.progress,
    nextBtnText: text.next,
    prevBtnText: text.previous,
    doneBtnText: text.done,
    onPopoverRender: popover => {
      popover.closeButton.textContent = text.close
      popover.closeButton.title = text.close
      popover.closeButton.setAttribute('aria-label', text.close)
    },
    onDestroyed: () => {
      if (!closing && tutorial.active.value) finish('interrupted')
    },
  })
  driverInstance.drive(startIndex)
}

watch(() => tutorial.active.value, active => {
  if (active) void launch(0)
  else {
    abortController?.abort()
    driverInstance?.destroy()
    driverInstance = null
  }
})

watch(currentLocale, () => {
  if (tutorial.active.value) void launch(tutorial.nodeIndex.value)
})

onBeforeUnmount(() => {
  abortController?.abort()
  driverInstance?.destroy()
  if (tutorial.active.value) tutorial.stop('interrupted')
})
</script>

<template><span class="hidden" aria-hidden="true">{{ labels().close }}</span></template>
