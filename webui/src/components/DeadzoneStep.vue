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
  ArrowLeft, 
  ArrowRight, 
  Activity, 
  Radio
} from 'lucide-vue-next'
import type { RangeMode } from '../types/api'

import { api } from '../services/api'

const sessionStore = useSessionStore()

const currentStep = ref<number>(0.005)
const activeProbeTarget = ref<'inner' | 'outer'>('inner')
const isMeasuringNoise = ref<boolean>(false)

const probeActive = computed(() => sessionStore.probe?.active ?? false)
const expiresCountdown = computed(() => sessionStore.probe?.expires_in ?? 0)

const config = computed(() => sessionStore.config)
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
      await api.wakeController(config.value?.wake_input || 'right_stick')
    } catch {
      // ignore
    }
  }
}

async function onInnerUpdate(val: number) {
  await autoWakeIfNeeded()
  await sessionStore.updateConfig({ inner_deadzone: val })
  if (probeActive.value && activeProbeTarget.value === 'inner') {
    await sessionStore.updateDeadzoneProbe(val)
  }
}

async function onOuterUpdate(val: number) {
  await autoWakeIfNeeded()
  await sessionStore.updateConfig({ outer_deadzone: val })
  if (probeActive.value && activeProbeTarget.value === 'outer') {
    await sessionStore.updateDeadzoneProbe(val)
  }
}

async function onPointCountUpdate(count: number) {
  await sessionStore.updateConfig({ point_count: count })
}

async function onRangeModeUpdate(mode: RangeMode) {
  await sessionStore.updateConfig({ range_mode: mode })
}

async function onProbeOutput(val: number) {
  if (probeActive.value) {
    await sessionStore.updateDeadzoneProbe(val)
  }
}

onBeforeUnmount(() => {
  if (probeActive.value) {
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

function goBack() {
  sessionStore.activeStep = 1
}

function proceedToMeasurement() {
  sessionStore.activeStep = 3
}
</script>

<template>
  <div class="space-y-6">
    <!-- Top Interactive Probing Bar -->
    <div class="p-4 bg-white border border-neutral-200/80 rounded-xl shadow-xs space-y-4">
      <div class="flex items-center justify-between border-b border-neutral-100 pb-3 flex-wrap gap-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-8 h-8 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center">
            <Target class="w-4 h-4" />
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">
                摇杆实时输出微调与死区验证
              </h3>
              <span
                v-if="probeActive"
                class="flex items-center space-x-1.5 px-2 py-0.5 bg-neutral-900 text-white rounded-full text-[11px] font-mono"
              >
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>推杆输出中 ({{ expiresCountdown }}s)</span>
              </span>
            </div>
            <p class="text-[11px] text-neutral-400">
              激活后实时输出当前选中的死区点数值，观察游戏视口画面微动以精确测定死区边界
            </p>
          </div>
        </div>

        <!-- Master Output Switcher Button -->
        <div>
          <button
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
        <div class="md:col-span-6 flex items-center space-x-3">
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
    />

    <!-- Bottom Row: Noise Benchmark & Step Navigation -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
      <!-- Noise Floor Benchmark Card (7 cols) -->
      <div class="lg:col-span-7 p-4 bg-white border border-neutral-200/80 rounded-xl space-y-2.5 shadow-xs">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-neutral-600">
            <Activity class="w-3.5 h-3.5 text-neutral-700" />
            <span>画面静止噪底校准 (Noise Floor)</span>
          </div>
          <button
            type="button"
            @click="runNoiseBenchmark"
            :disabled="isMeasuringNoise"
            class="text-xs bg-neutral-900 hover:bg-neutral-800 disabled:opacity-40 text-white px-3 py-1 rounded-md transition cursor-pointer font-medium"
          >
            {{ isMeasuringNoise ? '采样中...' : '测定噪底' }}
          </button>
        </div>
        <p class="text-[11px] text-neutral-500">
          采样游戏画面在手柄回中完全静止时的背景微晃与噪点，用于在后续曲线测定中准确过滤环境噪底。
        </p>
        <div v-if="sessionStore.noise" class="p-2.5 bg-neutral-50 border border-neutral-200/60 rounded-lg text-xs font-mono text-neutral-700 flex justify-between">
          <span>X 轴噪底: {{ sessionStore.noise.floor_x }} px/s</span>
          <span>Y 轴噪底: {{ sessionStore.noise.floor_y }} px/s</span>
        </div>
      </div>

      <!-- Navigation Buttons (5 cols) -->
      <div class="lg:col-span-5 flex items-center space-x-3">
        <button
          type="button"
          @click="goBack"
          class="flex-1 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 font-medium py-3 px-4 rounded-lg flex items-center justify-center space-x-2 transition cursor-pointer text-xs"
        >
          <ArrowLeft class="w-4 h-4" />
          <span>{{ t('step_1_title') }}</span>
        </button>
        <button
          type="button"
          @click="proceedToMeasurement"
          class="flex-1 bg-neutral-900 hover:bg-neutral-800 text-white font-medium py-3 px-4 rounded-lg flex items-center justify-center space-x-2 transition cursor-pointer text-xs shadow-xs"
        >
          <span>{{ t('proceed_to_measurement') }}</span>
          <ArrowRight class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>
