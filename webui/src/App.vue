<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useConnectionStore } from './stores/connection'
import { useSessionStore } from './stores/session'
import { api } from './services/api'
import { initiateApplicationShutdown } from './services/appShutdown'
import { soundSynth } from './services/sound'
import { ws } from './services/ws'
import { t, currentLocale, setLocale } from './services/i18n'
import CaptureStep from './components/CaptureStep.vue'
import DeadzoneStep from './components/DeadzoneStep.vue'
import MeasurementStep from './components/MeasurementStep.vue'
import HotkeySettingsModal from './components/HotkeySettingsModal.vue'
import CountdownModal from './components/CountdownModal.vue'
import TutorialOverlay from './components/TutorialOverlay.vue'
import VigemWarningModal from './components/VigemWarningModal.vue'
import { createTutorialController, provideTutorial } from './composables/useTutorial'
import { hasCompletedTutorial } from './services/tutorialState'
import { dismissVigemWarning, shouldShowVigemWarning } from './services/vigemWarning'
const AnalysisStep = defineAsyncComponent(() => import('./components/AnalysisStep.vue'))
import { 
  Monitor, 
  Target, 
  Activity, 
  BarChart3, 
  Gamepad2, 
  Power,
  Settings,
  Globe,
  ArrowLeft,
  ArrowRight,
  RotateCcw
} from 'lucide-vue-next'

const connectionStore = useConnectionStore()
const sessionStore = useSessionStore()
const isQuitting = ref(false)
const showHotkeyModal = ref(false)
const showVigemWarning = ref(false)
const tutorial = provideTutorial(createTutorialController({
  getPage: () => sessionStore.activeStep,
  setPage: page => { sessionStore.activeStep = page },
}))
const headerCapture = computed(() => tutorial.active.value ? tutorial.demo.capture : sessionStore.capture)

async function startTutorialFromSettings() {
  showHotkeyModal.value = false
  await nextTick()
  tutorial.start('settings')
}

function closeVigemWarning(neverRemind: boolean) {
  if (neverRemind) dismissVigemWarning()
  showVigemWarning.value = false
  if (!hasCompletedTutorial()) tutorial.start('first-run')
}

async function toggleController() {
  try {
    await connectionStore.setControllerEnabled(!connectionStore.controllerEnabled)
  } catch (err: any) {
    window.alert(err.message || t('toggle_controller_failed'))
  }
}

const steps = computed(() => [
  { id: 1, title: t('step_1_title'), desc: t('step_1_desc'), icon: Monitor },
  { id: 2, title: t('step_2_title'), desc: t('step_2_desc'), icon: Target },
  { id: 3, title: t('step_3_title'), desc: t('step_3_desc'), icon: Activity },
  { id: 4, title: t('step_4_title'), desc: t('step_4_desc'), icon: BarChart3 },
])

const canGoPrev = computed(() => {
  if (sessionStore.activeStep <= 1) return false
  if (sessionStore.activeStep === 3 && sessionStore.activeJob !== null) return false
  return true
})

const canGoNext = computed(() => {
  switch (sessionStore.activeStep) {
    case 1:
      return Boolean(
        sessionStore.capture &&
        sessionStore.roi &&
        (sessionStore.roiQuality ? sessionStore.roiQuality.score >= 25 : true)
      )
    case 2:
      return true
    case 3:
      return Boolean(sessionStore.activeJob === null && sessionStore.lastResult)
    case 4:
      return true
    default:
      return false
  }
})

const nextTooltip = computed(() => {
  if (canGoNext.value) return ''
  if (sessionStore.activeStep === 1) {
    if (!sessionStore.capture) return t('select_window_signal_hint')
    if (!sessionStore.roi) return t('roi_instruction')
    if (sessionStore.roiQuality && sessionStore.roiQuality.score < 25) return t('region_too_flat')
  } else if (sessionStore.activeStep === 3) {
    if (sessionStore.activeJob !== null) return t('phase_running')
    if (!sessionStore.lastResult) return t('start_probe')
  }
  return ''
})

function navigatePrev() {
  if (!canGoPrev.value) return
  if (sessionStore.activeStep > 1) {
    sessionStore.activeStep--
  }
}

function navigateNext() {
  if (!canGoNext.value) return
  if (sessionStore.activeStep < 4) {
    sessionStore.activeStep++
  } else if (sessionStore.activeStep === 4) {
    sessionStore.activeStep = 3
  }
}

async function quitApplication() {
  if (!window.confirm(t('quit_confirm'))) {
    return
  }

  isQuitting.value = true
  initiateApplicationShutdown(
    () => api.quitApplication(),
    () => ws.close(),
    () => window.close(),
  )
  window.setTimeout(() => {
    isQuitting.value = false
  }, 1000)
}

function handleKeyDown(event: KeyboardEvent) {
  if (tutorial.active.value) return
  // Ignore hotkey triggers when user is typing in an input/textarea/select
  const target = event.target as HTMLElement | null
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT')) {
    return
  }

  const cfg = sessionStore.config
  if (!cfg || cfg.hotkey_enabled === false) return

  const startKey = (cfg.hotkey_start || 'F9').toUpperCase()
  const stopKey = (cfg.hotkey_stop || 'F10').toUpperCase()
  const dzIncKey = (cfg.hotkey_dz_inc || 'F7').toUpperCase()
  const dzDecKey = (cfg.hotkey_dz_dec || 'F6').toUpperCase()

  const pressedKey = event.key.toUpperCase()

  if (pressedKey === startKey || (startKey === 'F9' && event.key === 'F9')) {
    event.preventDefault()
    if (!sessionStore.activeJob) {
      sessionStore.startMeasurement()
      if (cfg.sound_enabled !== false) {
        soundSynth.playStartSound()
      }
    }
  } else if (pressedKey === stopKey || (stopKey === 'F10' && event.key === 'F10')) {
    event.preventDefault()
    if (sessionStore.activeJob?.id) {
      sessionStore.cancelJob(sessionStore.activeJob.id)
      if (cfg.sound_enabled !== false) {
        soundSynth.playStopSound()
      }
    }
  } else if (pressedKey === dzIncKey || (dzIncKey === 'F7' && event.key === 'F7')) {
    event.preventDefault()
    adjustDeadzoneInFrontend(1)
  } else if (pressedKey === dzDecKey || (dzDecKey === 'F6' && event.key === 'F6')) {
    event.preventDefault()
    adjustDeadzoneInFrontend(-1)
  }
}

async function adjustDeadzoneInFrontend(direction: number) {
  const cfg = sessionStore.config
  if (!cfg) return
  const target = cfg.dz_target || 'inner'
  const step = cfg.dz_step || 0.005
  const delta = direction * step

  if (cfg.auto_wake !== false) {
    try {
      await api.wakeController(cfg.wake_input || 'left_stick')
    } catch {
      // ignore
    }
  }

  if (target === 'inner') {
    const safeOuter = cfg.outer_deadzone ?? 0.95
    const inner = cfg.inner_deadzone ?? 0.05
    const newInner = Math.round(Math.max(0.0, Math.min(safeOuter - 0.01, inner + delta)) * 10000) / 10000
    await sessionStore.updateConfig({ inner_deadzone: newInner })
    if (sessionStore.probe?.active) {
      await sessionStore.updateDeadzoneProbe(newInner)
    }
  } else {
    const safeInner = cfg.inner_deadzone ?? 0.05
    const outer = cfg.outer_deadzone ?? 0.95
    const newOuter = Math.round(Math.max(safeInner + 0.01, Math.min(1.0, outer + delta)) * 10000) / 10000
    await sessionStore.updateConfig({ outer_deadzone: newOuter })
    if (sessionStore.probe?.active) {
      await sessionStore.updateDeadzoneProbe(newOuter)
    }
  }

  if (cfg.sound_enabled !== false) {
    soundSynth.playTestSound()
  }
}

onMounted(async () => {
  const healthCheckSucceeded = await connectionStore.checkHealth()
  sessionStore.initListeners()
  ws.connectEvents()
  ws.connectPreview()
  await sessionStore.loadInitialData()
  await nextTick()
  showVigemWarning.value = shouldShowVigemWarning(healthCheckSucceeded, connectionStore.controllerReady)
  if (!showVigemWarning.value && !hasCompletedTutorial()) tutorial.start('first-run')
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <div class="min-h-screen bg-neutral-50 text-neutral-900 flex flex-col font-sans">
    <!-- Top Navigation Bar -->
    <header class="border-b border-neutral-200/80 bg-white sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 rounded-lg bg-neutral-900 flex items-center justify-center text-white">
            <Gamepad2 class="w-4 h-4" />
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h1 class="text-sm font-semibold tracking-tight text-neutral-900">
                GameCurveProbe
              </h1>
              <span class="text-[10px] px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-500 font-mono">v2.0</span>
            </div>
            <p class="text-[11px] text-neutral-400">{{ t('app_subtitle') }}</p>
          </div>
        </div>

        <div class="flex items-center space-x-3 text-xs">
          <div class="flex items-center space-x-2 px-2.5 py-1 rounded-md bg-neutral-100 text-neutral-600 text-[11px]">
            <span v-if="connectionStore.connected" class="flex items-center text-neutral-700 font-medium">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5"></span>
              {{ t('connected') }}
            </span>
            <span v-else class="flex items-center text-rose-600 font-medium">
              <span class="w-1.5 h-1.5 rounded-full bg-rose-500 mr-1.5"></span>
              {{ t('disconnected') }}
            </span>
            <span class="text-neutral-300">|</span>
            <span v-if="headerCapture" class="text-neutral-600 font-mono">
              {{ headerCapture.backend.toUpperCase() }} {{ headerCapture.width }}×{{ headerCapture.height }}
            </span>
            <span v-else class="text-neutral-400">
              {{ t('no_window_captured') }}
            </span>
          </div>

          <!-- Settings button -->
          <button
            type="button"
            class="flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 transition cursor-pointer border border-neutral-200/80"
            :title="t('settings')"
            @click="showHotkeyModal = true"
          >
            <Settings class="w-3.5 h-3.5 text-neutral-700" />
            <span>{{ t('settings') }}</span>
          </button>

          <label
            data-tour="controller-status"
            class="flex items-center gap-2 px-2.5 py-1 rounded-md text-[11px] font-medium text-neutral-600 hover:bg-neutral-100 cursor-pointer"
            :class="{ 'opacity-50 cursor-wait': connectionStore.isUpdatingController }"
            :title="t('vigem_toggle_tooltip')"
          >
            <span>ViGEmBus</span>
            <input
              type="checkbox"
              class="sr-only peer"
              :checked="connectionStore.controllerEnabled"
              :disabled="connectionStore.isUpdatingController || !connectionStore.controllerReady"
              :aria-label="t('controller_enable')"
              @change="toggleController"
            />
            <span class="relative w-7 h-4 rounded-full bg-neutral-300 peer-checked:bg-emerald-500 transition-colors after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:w-3 after:h-3 after:rounded-full after:bg-white after:transition-transform peer-checked:after:translate-x-3"></span>
          </label>

          <!-- Language Switcher -->
          <button
            type="button"
            class="flex items-center space-x-1 px-2.5 py-1 rounded-md text-[11px] font-medium text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 transition cursor-pointer border border-neutral-200/80"
            :title="t('lang_switcher_tooltip')"
            @click="setLocale(currentLocale === 'zh' ? 'en' : 'zh')"
          >
            <Globe class="w-3.5 h-3.5 text-neutral-700" />
            <span class="font-mono font-bold">{{ currentLocale === 'zh' ? 'EN' : '中' }}</span>
          </button>

          <button
            type="button"
            :disabled="isQuitting"
            :title="t('quit_tooltip')"
            class="flex items-center space-x-1 px-2.5 py-1 rounded-md text-[11px] font-medium text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100 transition disabled:opacity-50 cursor-pointer"
            @click="quitApplication"
          >
            <Power class="w-3.5 h-3.5" />
            <span>{{ isQuitting ? t('quitting') : t('quit') }}</span>
          </button>
        </div>
      </div>
    </header>

    <!-- Guided Steps Navigation (Minimalist Segmented) -->
    <div class="border-b border-neutral-200/60 bg-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6">
        <nav data-tour="workflow-nav" class="flex space-x-1 sm:space-x-2 py-2">
          <button
            v-for="step in steps"
            :key="step.id"
            @click="sessionStore.activeStep = step.id"
            class="flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer"
            :class="[
              sessionStore.activeStep === step.id
                ? 'bg-neutral-900 text-white shadow-sm'
                : 'text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100'
            ]"
          >
            <component :is="step.icon" class="w-3.5 h-3.5" />
            <span>{{ step.id }}. {{ step.title }}</span>
          </button>
        </nav>
      </div>
    </div>

    <!-- Main Content Container (Open & Breathable, No Nested Panels) -->
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 pb-28">
      <div v-if="sessionStore.activeStep === 1">
        <CaptureStep />
      </div>
      <div v-else-if="sessionStore.activeStep === 2">
        <DeadzoneStep />
      </div>
      <div v-else-if="sessionStore.activeStep === 3">
        <MeasurementStep />
      </div>
      <div v-else-if="sessionStore.activeStep === 4">
        <AnalysisStep />
      </div>
    </main>

    <!-- Sticky Bottom Navigation Bar (Centered) -->
    <footer class="sticky bottom-0 z-40 bg-white/90 backdrop-blur-md border-t border-neutral-200/80 shadow-xs py-3 px-4">
      <div class="max-w-7xl mx-auto flex items-center justify-center gap-4">
        <!-- Previous Step Button -->
        <button
          v-if="sessionStore.activeStep > 1"
          type="button"
          @click="navigatePrev"
          :disabled="!canGoPrev"
          class="min-w-[160px] inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg border border-neutral-200 bg-white hover:bg-neutral-50 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-medium text-neutral-700 transition cursor-pointer shadow-xs"
        >
          <ArrowLeft class="w-4 h-4" />
          <span>
            {{
              sessionStore.activeStep === 2
                ? t('back_to_capture')
                : sessionStore.activeStep === 3
                ? t('back_to_deadzone')
                : t('back_to_measurement')
            }}
          </span>
        </button>

        <!-- Next / Action Button -->
        <button
          type="button"
          @click="navigateNext"
          :disabled="!canGoNext"
          :title="nextTooltip"
          class="min-w-[160px] inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-neutral-900 hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-medium text-white transition cursor-pointer shadow-xs"
        >
          <span>
            {{
              sessionStore.activeStep === 1
                ? t('proceed_to_deadzone')
                : sessionStore.activeStep === 2
                ? t('proceed_to_measurement')
                : sessionStore.activeStep === 3
                ? t('proceed_to_analysis')
                : t('restart_test')
            }}
          </span>
          <RotateCcw v-if="sessionStore.activeStep === 4" class="w-4 h-4" />
          <ArrowRight v-else class="w-4 h-4" />
        </button>
      </div>
    </footer>

    <!-- Hotkey & Sound Settings Modal -->
    <HotkeySettingsModal
      :show="showHotkeyModal"
      @close="showHotkeyModal = false"
      @start-tutorial="startTutorialFromSettings"
    />

    <!-- Measurement Countdown Modal -->
    <CountdownModal />
    <VigemWarningModal :show="showVigemWarning" @close="closeVigemWarning" />
    <TutorialOverlay />
  </div>
</template>
