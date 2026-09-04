<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useSessionStore } from '../stores/session'
import { createProbeLease } from '../services/probeLease'
import DeadzoneRangeSlider from './DeadzoneRangeSlider.vue'
import { t } from '../services/i18n'
import { 
  Target, 
  Play, 
  Square, 
  Activity, 
  Radio
} from 'lucide-vue-next'
import type { RangeMode } from '../types/api'

import { api } from '../services/api'
import { shouldDisposeRealProbe, useTutorial } from '../composables/useTutorial'

const sessionStore = useSessionStore()
const tutorial = useTutorial()

const currentStep = ref<number>(0.005)
const activeProbeTarget = ref<'inner' | 'outer'>('inner')
const isMeasuringNoise = ref<boolean>(false)

const probeActive = computed(() => tutorial.active.value && tutorial.phase.value === 'show-probe' ? true : (sessionStore.probe?.active ?? false))
const expiresCountdown = computed(() => tutorial.active.value ? tutorial.demo.probe.expires_in : (sessionStore.probe?.expires_in ?? 0))

const config = computed(() => tutorial.active.value ? tutorial.demo.config : sessionStore.config)
const innerDeadzone = computed(() => config.value?.inner_deadzone ?? 0.05)
const outerDeadzone = computed(() => config.value?.outer_deadzone ?? 0.95)
const pointCount = computed(() => config.value?.point_count ?? 17)
const rangeMode = computed<RangeMode>(() => config.value?.range_mode ?? 'active_range')

watch(
  config,
  (cfg) => {
    if (cfg) {
      if (cfg.dz_target) activeProbeTarget.value = cfg.dz_target
      if (cfg.dz_step) currentStep.value = cfg.dz_step
    }
  },
  { immediate: true }
)

const currentProbeOutput = computed(() => {
  return activeProbeTarget.value === 'inner' ? innerDeadzone.value : outerDeadzone.value
})

const probeLease = createProbeLease(
  () => sessionStore.updateDeadzoneProbe(currentProbeOutput.value),
  () => sessionStore.stopDeadzoneProbe(),
)

async function toggleProbe() {
  if (probeActive.value) {
    probeLease.pause()
    await sessionStore.stopDeadzoneProbe()
  } else {
    await sessionStore.startDeadzoneProbe(currentProbeOutput.value, currentStep.value)
    probeLease.start()
  }
}

async function selectProbeTarget(target: 'inner' | 'outer') {
  activeProbeTarget.value = target
  await sessionStore.updateConfig({ dz_target: target })
  if (probeActive.value) {
    const output = target === 'inner' ? innerDeadzone.value : outerDeadzone.value
    await sessionStore.updateDeadzoneProbe(output)
  }
}

async function setStep(step: number) {
  currentStep.value = step
  await sessionStore.updateConfig({ dz_step: step })
}

async function autoWakeIfNeeded() {
  if (config.value?.auto_wake !== false) {
    try {
      await api.wakeController(config.value?.wake_input || 'left_stick')
    } catch {
      // ignore
    }
  }
}

let configDebounceTimer: ReturnType<typeof setTimeout> | null = null
let pendingConfigChanges: Partial<any> = {}

function scheduleConfigUpdate(changes: Record<string, any>, immediate = false) {
  pendingConfigChanges = { ...pendingConfigChanges, ...changes }
  if (configDebounceTimer) {
    clearTimeout(configDebounceTimer)
    configDebounceTimer = null
  }
  const flush = async () => {
    const toSave = { ...pendingConfigChanges }
    pendingConfigChanges = {}
    await autoWakeIfNeeded()
    await sessionStore.updateConfig(toSave)
  }
  if (immediate) {
    void flush()
  } else {
    configDebounceTimer = setTimeout(flush, 150)
  }
}

async function onInnerUpdate(val: number) {
  if (sessionStore.config) {
    sessionStore.config.inner_deadzone = val
  }
  scheduleConfigUpdate({ inner_deadzone: val }, false)
}

async function onOuterUpdate(val: number) {
  if (sessionStore.config) {
    sessionStore.config.outer_deadzone = val
  }
  scheduleConfigUpdate({ outer_deadzone: val }, false)
}

async function onSliderChange(payload: { inner: number; outer: number; target: 'inner' | 'outer' }) {
  scheduleConfigUpdate({
    inner_deadzone: payload.inner,
    outer_deadzone: payload.outer,
  }, true)
  if (probeActive.value) {
    const output = payload.target === 'inner' ? payload.inner : payload.outer
    await sessionStore.updateDeadzoneProbe(output)
  }
}

async function onPointCountUpdate(count: number) {
  await sessionStore.updateConfig({ point_count: count })
}

async function onRangeModeUpdate(mode: RangeMode) {
  await sessionStore.updateConfig({ range_mode: mode })
}

let pendingProbeVal: number | null = null
let probeRaf: number | null = null

function onProbeOutput(val: number) {
  if (!probeActive.value) return
  pendingProbeVal = val
  if (probeRaf !== null) return
  probeRaf = requestAnimationFrame(async () => {
    probeRaf = null
    if (pendingProbeVal !== null && probeActive.value) {
      const out = pendingProbeVal
      pendingProbeVal = null
      try {
        await sessionStore.updateDeadzoneProbe(out)
      } catch {
        // ignore
      }
    }
  })
}

onBeforeUnmount(() => {
  if (configDebounceTimer) clearTimeout(configDebounceTimer)
  if (probeRaf !== null) cancelAnimationFrame(probeRaf)
  if (shouldDisposeRealProbe(tutorial.active.value, probeActive.value)) {
    void probeLease.dispose()
  } else {
    probeLease.pause()
  }
})

async function runNoiseBenchmark() {
  isMeasuringNoise.value = true
  try {
    await sessionStore.startIdleNoise()
  } catch (err) {
    console.error('Failed to run noise test:', err)
  } finally {
    isMeasuringNoise.value = false
  }
}
</script>

<template>
  <div data-tour="deadzone-overview" class="space-y-6">
    <!-- Top Interactive Probing Bar -->
    <div class="p-4 bg-white border border-neutral-200/80 rounded-xl shadow-xs space-y-4">
      <div class="flex items-center justify-between border-b border-neutral-100 pb-3 flex-wrap gap-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
            <Target class="w-4 h-4" />
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">
                {{ t('deadzone_verify_title') }}
              </h3>
              <span
                v-if="probeActive"
                class="flex items-center space-x-1.5 px-2 py-0.5 bg-neutral-900 text-white rounded-full text-[11px] font-mono"
              >
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>{{ t('outputting_pulse') }} ({{ expiresCountdown }}s)</span>
              </span>
            </div>
            <p class="text-[11px] text-neutral-400">
              {{ t('probe_running_hint') }}
            </p>
          </div>
        </div>

        <!-- Master Output Switcher Button -->
        <div>
          <button
            data-tour="probe-toggle"
            @click="toggleProbe"
            class="py-2 px-4 rounded-lg font-medium text-xs flex items-center justify-center space-x-2 transition cursor-pointer shadow-xs"
            :class="[
              probeActive
                ? 'bg-rose-600 hover:bg-rose-700 text-white'
                : 'bg-neutral-900 hover:bg-neutral-800 text-white'
            ]"
          >
            <Square v-if="probeActive" class="w-3.5 h-3.5 fill-current" />
            <Play v-else class="w-3.5 h-3.5 fill-current" />
            <span>{{ probeActive ? t('stop_probe') : t('start_probe') }}</span>
          </button>
        </div>
      </div>

      <!-- Probing Targets & Step Selector Row -->
      <div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
        <!-- Target Selector (6 cols) -->
        <div data-tour="probe-targets" class="md:col-span-6 flex items-center space-x-3">
          <span class="text-xs text-neutral-500 shrink-0">{{ t('probe_target') }}:</span>
          <div class="flex rounded-lg bg-neutral-100 p-0.5 text-xs font-medium text-neutral-600 flex-1">
            <button
              type="button"
              @click="selectProbeTarget('inner')"
              class="flex-1 py-1.5 px-3 rounded-md transition cursor-pointer flex items-center justify-center space-x-1.5"
              :class="activeProbeTarget === 'inner' ? 'bg-white text-neutral-900 shadow-xs font-bold' : 'hover:text-neutral-900'"
            >
              <Radio class="w-3.5 h-3.5" :class="activeProbeTarget === 'inner' ? 'text-neutral-900' : 'text-neutral-400'" />
              <span>{{ t('inner_deadzone') }}: {{ (innerDeadzone * 100).toFixed(1) }}%</span>
            </button>
            <button
              type="button"
              @click="selectProbeTarget('outer')"
              class="flex-1 py-1.5 px-3 rounded-md transition cursor-pointer flex items-center justify-center space-x-1.5"
              :class="activeProbeTarget === 'outer' ? 'bg-white text-neutral-900 shadow-xs font-bold' : 'hover:text-neutral-900'"
            >
              <Radio class="w-3.5 h-3.5" :class="activeProbeTarget === 'outer' ? 'text-neutral-900' : 'text-neutral-400'" />
              <span>{{ t('outer_deadzone') }}: {{ (outerDeadzone * 100).toFixed(1) }}%</span>
            </button>
          </div>
        </div>

        <!-- Step Selector (6 cols) -->
        <div class="md:col-span-6 flex items-center space-x-3">
          <span class="text-xs text-neutral-500 shrink-0">{{ t('adjust_step') }}:</span>
          <div class="grid grid-cols-3 gap-1.5 flex-1">
            <button
              v-for="step in [0.001, 0.005, 0.01]"
              :key="step"
              type="button"
              @click="setStep(step)"
              class="py-1 px-2.5 rounded-lg text-xs font-mono font-medium transition cursor-pointer text-center"
              :class="[
                currentStep === step
                  ? 'bg-neutral-900 text-white'
                  : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200 hover:text-neutral-900'
              ]"
            >
              {{ step === 0.001 ? t('step_fine') : step === 0.005 ? t('step_standard') : t('step_fast') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Single-Axis Dual-Thumb Deadzone Range Slider & Predicted Points Visualizer -->
    <DeadzoneRangeSlider
      data-tour="deadzone-range"
      :inner-deadzone="innerDeadzone"
      :outer-deadzone="outerDeadzone"
      :point-count="pointCount"
      :range-mode="rangeMode"
      :probe-active="probeActive"
      :active-probe-target="activeProbeTarget"
      :step="currentStep"
      @update:inner-deadzone="onInnerUpdate"
      @update:outer-deadzone="onOuterUpdate"
      @update:point-count="onPointCountUpdate"
      @update:range-mode="onRangeModeUpdate"
      @update:active-probe-target="selectProbeTarget"
      @probe-output="onProbeOutput"
      @change="onSliderChange"
    />

    <!-- Noise Floor Benchmark Card -->
    <div data-tour="noise-test" class="p-4 bg-white border border-neutral-200/80 rounded-xl space-y-3 shadow-xs">
      <div class="flex items-center justify-between border-b border-neutral-100 pb-3 flex-wrap gap-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
            <Activity class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">
              {{ t('noise_calibration_title') }}
            </h3>
            <p class="text-[11px] text-neutral-400">
              {{ t('noise_desc') }}
            </p>
          </div>
        </div>
        <button
          type="button"
          @click="runNoiseBenchmark"
          :disabled="isMeasuringNoise"
          class="text-xs bg-neutral-900 hover:bg-neutral-800 disabled:opacity-40 text-white px-3 py-1.5 rounded-lg transition cursor-pointer font-medium shadow-xs"
        >
          {{ isMeasuringNoise ? t('noise_measuring') : t('measure_noise') }}
        </button>
      </div>
      <div v-if="sessionStore.noise || (tutorial.active.value && tutorial.phase.value === 'show-noise')" class="p-2.5 bg-neutral-50 border border-neutral-200/60 rounded-lg text-xs font-mono text-neutral-700 flex justify-between">
        <span>{{ t('noise_x') }}: {{ tutorial.active.value ? tutorial.demo.noise.floor_x : sessionStore.noise?.floor_x }} px/s</span>
        <span>{{ t('noise_y') }}: {{ tutorial.active.value ? tutorial.demo.noise.floor_y : sessionStore.noise?.floor_y }} px/s</span>
      </div>
    </div>
  </div>
</template>
