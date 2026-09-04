<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useSessionStore } from '../stores/session'
import { t } from '../services/i18n'
import { 
  Activity, 
  Play, 
  Square, 
  Sliders, 
  CheckCircle2, 
  AlertCircle,
  Clock,
  Terminal,
  Copy,
  Check,
  Trash2,
  ArrowDown,
  Camera,
  Crosshair
} from 'lucide-vue-next'
import type { RangeMode } from '../types/api'

import CountdownModal from './CountdownModal.vue'

const sessionStore = useSessionStore()
const showCountdown = ref(false)
const rangeMode = ref<RangeMode>(sessionStore.config?.range_mode || 'full')

// Point Count Presets & Custom Input
const initialPointCount = sessionStore.config?.point_count || 17
const pointCountPreset = ref<string>(
  [9, 17, 33].includes(initialPointCount) ? String(initialPointCount) : 'custom'
)
const customPointCount = ref<number>(initialPointCount)

const pointCount = computed<number>(() => {
  if (pointCountPreset.value === 'custom') {
    return Math.max(3, Math.min(100, customPointCount.value || 17))
  }
  return parseInt(pointCountPreset.value, 10) || 17
})

// Duration Presets & Custom Input
const initialSettleMs = sessionStore.config?.settle_ms || 300
const initialSampleMs = sessionStore.config?.sample_ms || 700

const getInitialDurationPreset = () => {
  if (initialSettleMs === 300 && initialSampleMs === 700) return 'standard'
  if (initialSettleMs === 200 && initialSampleMs === 500) return 'fast'
  if (initialSettleMs === 400 && initialSampleMs === 1000) return 'precise'
  return 'custom'
}

const durationPreset = ref<string>(getInitialDurationPreset())
const customSettleMs = ref<number>(initialSettleMs)
const customSampleMs = ref<number>(initialSampleMs)

const settleMs = computed<number>(() => {
  if (durationPreset.value === 'standard') return 300
  if (durationPreset.value === 'fast') return 200
  if (durationPreset.value === 'precise') return 400
  return Math.max(50, Math.min(5000, customSettleMs.value || 300))
})

const sampleMs = computed<number>(() => {
  if (durationPreset.value === 'standard') return 700
  if (durationPreset.value === 'fast') return 500
  if (durationPreset.value === 'precise') return 1000
  return Math.max(100, Math.min(10000, customSampleMs.value || 700))
})

const estimatedDurationSec = computed<number>(() => {
  const pts = pointCount.value
  const singlePtSec = (settleMs.value + sampleMs.value) / 1000
  const totalMeasurements = pts <= 1 ? 1 : 1 + (pts - 1) * 2
  return Math.round(totalMeasurements * singlePtSec + (pts - 1) * 0.1)
})

watch(durationPreset, (newPreset, oldPreset) => {
  if (newPreset === 'custom') {
    if (oldPreset === 'standard') {
      customSettleMs.value = 300
      customSampleMs.value = 700
    } else if (oldPreset === 'fast') {
      customSettleMs.value = 200
      customSampleMs.value = 500
    } else if (oldPreset === 'precise') {
      customSettleMs.value = 400
      customSampleMs.value = 1000
    }
  }
})

watch(pointCountPreset, (newPreset, oldPreset) => {
  if (newPreset === 'custom') {
    const num = parseInt(oldPreset, 10)
    if (!isNaN(num)) {
      customPointCount.value = num
    }
  }
})

const errorMessage = ref<string | null>(null)

const logContainerRef = ref<HTMLElement | null>(null)
const autoScroll = ref(true)
const copied = ref(false)

const activeJob = computed(() => sessionStore.activeJob)
const isRunning = computed(() => activeJob.value?.state === 'running' || activeJob.value?.state === 'queued' || activeJob.value?.state === 'canceling')
const progressData = computed(() => activeJob.value?.progress)
const currentPoint = computed(() => progressData.value?.current_point || 0)
const totalPoints = computed(() => progressData.value?.total_points || pointCount.value)
const progressPercent = computed(() => {
  if (!totalPoints.value || totalPoints.value === 0) return 0
  return Math.round((currentPoint.value / totalPoints.value) * 100)
})

const lastResult = computed(() => sessionStore.lastResult)

const currentPhase = computed(() => progressData.value?.phase || (isRunning.value ? 'running' : 'idle'))
const phaseText = computed(() => {
  switch (currentPhase.value) {
    case 'stage_start': return t('phase_stage_start')
    case 'point_settle': return t('phase_point_settle')
    case 'point_sampling': return t('phase_point_sampling')
    case 'point_retry': return t('phase_point_retry')
    case 'point_done': return t('phase_point_done')
    case 'stage_completed': return t('phase_stage_completed')
    default: return isRunning.value ? t('phase_running') : t('phase_idle')
  }
})

const currentInputValue = computed(() => {
  if (progressData.value?.input_value !== undefined) {
    return progressData.value.input_value
  }
  return 0
})

const roiBoxStyle = computed(() => {
  if (!sessionStore.roi || !sessionStore.capture) return null
  const { x, y, width, height } = sessionStore.roi
  const capW = sessionStore.capture.width || 1920
  const capH = sessionStore.capture.height || 1080
  return {
    left: `${(x / capW) * 100}%`,
    top: `${(y / capH) * 100}%`,
    width: `${(width / capW) * 100}%`,
    height: `${(height / capH) * 100}%`,
  }
})

const displayPoints = computed(() => {
  if (isRunning.value && sessionStore.livePoints.length > 0) {
    return sessionStore.livePoints
  }
  if (lastResult.value?.points && lastResult.value.points.length > 0) {
    return lastResult.value.points
  }
  return sessionStore.livePoints
})

function onLogScroll() {
  if (!logContainerRef.value) return
  const { scrollTop, scrollHeight, clientHeight } = logContainerRef.value
  autoScroll.value = scrollHeight - (scrollTop + clientHeight) < 30
}

function scrollToBottom() {
  if (logContainerRef.value) {
    logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    autoScroll.value = true
  }
}

watch(
  () => sessionStore.measurementLogs.length,
  async () => {
    if (autoScroll.value) {
      await nextTick()
      if (logContainerRef.value) {
        logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
      }
    }
  }
)

async function copyLogs() {
  const text = sessionStore.measurementLogs
    .map(l => `[${l.timestamp}] [${l.level.toUpperCase()}] ${l.message}`)
    .join('\n')
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch (err) {
    console.error('Failed to copy logs:', err)
  }
}

function getLogLevelClass(level: string) {
  switch (level) {
    case 'action': return 'bg-neutral-100 text-neutral-800 border-neutral-200'
    case 'settle': return 'bg-neutral-100 text-neutral-700 border-neutral-200'
    case 'sampling': return 'bg-neutral-100 text-neutral-700 border-neutral-200'
    case 'warn': return 'bg-neutral-200 text-neutral-900 border-neutral-300'
    case 'success': return 'bg-neutral-900 text-white border-neutral-900'
    case 'error': return 'bg-rose-600 text-white border-rose-600'
    default: return 'bg-neutral-100 text-neutral-600 border-neutral-200'
  }
}

async function applyConfig() {
  await sessionStore.updateConfig({
    range_mode: rangeMode.value,
    point_count: pointCount.value,
    settle_ms: settleMs.value,
    sample_ms: sampleMs.value,
    bidirectional: true,
  })
}

async function startMeasurement() {
  errorMessage.value = null
  try {
    await applyConfig()
    await sessionStore.startMeasurement(rangeMode.value)
    showCountdown.value = true
  } catch (err: any) {
    errorMessage.value = err.message || t('start_measurement_err')
  }
}

async function cancelMeasurement() {
  if (activeJob.value?.id) {
    await sessionStore.cancelJob(activeJob.value.id)
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Config Bar -->
    <div class="p-4 bg-white border border-neutral-200/80 rounded-xl space-y-4 shadow-xs">
      <div class="flex items-center justify-between border-b border-neutral-100 pb-3 flex-wrap gap-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
            <Sliders class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">
              {{ t('measurement_param_config') }}
            </h3>
            <p class="text-[11px] text-neutral-400">
              {{ t('base_on_deadzone') }}: {{ t('inner_deadzone') }} {{ ((sessionStore.config?.inner_deadzone || 0) * 100).toFixed(1) }}%, {{ t('outer_deadzone') }} {{ ((sessionStore.config?.outer_deadzone || 1) * 100).toFixed(1) }}%
            </p>
          </div>
        </div>
      </div>

      <!-- Main Controls Row (Strictly aligned 4 columns) -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
        <!-- 测定范围模式 -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between h-4">
            <label class="text-xs font-medium text-neutral-700">{{ t('range_mode') }}</label>
          </div>
          <select
            v-model="rangeMode"
            :disabled="isRunning"
            class="w-full h-10 bg-neutral-50 hover:bg-white focus:bg-white border border-neutral-200 rounded-lg px-3 py-2 text-sm text-neutral-900 focus:outline-none focus:border-neutral-900 transition disabled:opacity-50"
          >
            <option value="full">{{ t('range_full') }}</option>
            <option value="active_range">{{ t('range_active') }}</option>
          </select>
        </div>

        <!-- 采样点密度 -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between h-4">
            <label class="text-xs font-medium text-neutral-700">{{ t('point_density') }}</label>
            <span v-if="pointCountPreset === 'custom'" class="text-[11px] font-mono text-neutral-500 font-medium">
              {{ pointCount }} {{ t('points_suffix') }}
            </span>
          </div>
          <select
            v-model="pointCountPreset"
            :disabled="isRunning"
            class="w-full h-10 bg-neutral-50 hover:bg-white focus:bg-white border border-neutral-200 rounded-lg px-3 py-2 text-sm text-neutral-900 focus:outline-none focus:border-neutral-900 transition disabled:opacity-50"
          >
            <option value="9">9 {{ t('points_suffix') }} (~15s)</option>
            <option value="17">17 {{ t('points_suffix') }} (~30s)</option>
            <option value="33">33 {{ t('points_suffix') }} (~60s)</option>
            <option value="custom">{{ t('custom_points') }}</option>
          </select>
        </div>

        <!-- 单点稳定/采样时长 -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between h-4">
            <label class="text-xs font-medium text-neutral-700">{{ t('settle_sample_duration') }}</label>
            <span class="text-[11px] font-mono text-neutral-500 font-medium">
              {{ settleMs }}ms / {{ sampleMs }}ms
            </span>
          </div>
          <select
            v-model="durationPreset"
            :disabled="isRunning"
            class="w-full h-10 bg-neutral-50 hover:bg-white focus:bg-white border border-neutral-200 rounded-lg px-3 py-2 text-sm text-neutral-900 focus:outline-none focus:border-neutral-900 transition disabled:opacity-50"
          >
            <option value="standard">{{ t('duration_standard') }}</option>
            <option value="fast">{{ t('duration_fast') }}</option>
            <option value="precise">{{ t('duration_precise') }}</option>
            <option value="custom">{{ t('duration_custom') }}</option>
          </select>
        </div>

        <!-- Start / Stop Button -->
        <div class="space-y-1.5">
          <div class="h-4"></div>
          <button
            v-if="!isRunning"
            type="button"
            @click="startMeasurement"
            class="w-full h-10 bg-neutral-900 hover:bg-neutral-800 text-white font-medium px-4 rounded-lg flex items-center justify-center space-x-2 transition cursor-pointer text-sm shadow-2xs active:scale-[0.99]"
          >
            <Play class="w-3.5 h-3.5 fill-current" />
            <span>{{ t('start_measurement') }}</span>
            <span v-if="sessionStore.config?.hotkey_enabled !== false" class="text-[10px] font-mono bg-white/20 px-1.5 py-0.5 rounded text-white/90 ml-1">
              [{{ sessionStore.config?.hotkey_start || 'F9' }}]
            </span>
          </button>
          <button
            v-else
            @click="cancelMeasurement"
            :disabled="activeJob?.state === 'canceling'"
            class="w-full h-10 bg-rose-600 hover:bg-rose-700 text-white font-medium px-4 rounded-lg flex items-center justify-center space-x-2 transition cursor-pointer text-sm disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.99]"
          >
            <Square class="w-3.5 h-3.5 fill-current" />
            <span>{{ activeJob?.state === 'canceling' ? t('canceling') : t('cancel_task') }}</span>
            <span v-if="sessionStore.config?.hotkey_enabled !== false" class="text-[10px] font-mono bg-white/20 px-1.5 py-0.5 rounded text-white/90 ml-1">
              [{{ sessionStore.config?.hotkey_stop || 'F10' }}]
            </span>
          </button>
        </div>
      </div>

      <!-- Custom Parameters Drawer (Smooth expansion below the controls) -->
      <transition
        enter-active-class="transition-all duration-200 ease-out"
        enter-from-class="opacity-0 -translate-y-1 max-h-0"
        enter-to-class="opacity-100 translate-y-0 max-h-40"
        leave-active-class="transition-all duration-150 ease-in"
        leave-from-class="opacity-100 translate-y-0 max-h-40"
        leave-to-class="opacity-0 -translate-y-1 max-h-0"
      >
        <div
          v-if="pointCountPreset === 'custom' || durationPreset === 'custom'"
          class="flex flex-wrap items-center justify-between gap-3 text-xs bg-neutral-50/80 p-3 rounded-xl border border-neutral-200/70"
        >
          <div class="flex flex-wrap items-center gap-4 sm:gap-6">
            <!-- Custom Point Count Input -->
            <div v-if="pointCountPreset === 'custom'" class="flex items-center space-x-2">
              <span class="text-xs font-medium text-neutral-700">{{ t('custom_points_label') }}:</span>
              <div class="relative flex items-center">
                <input
                  type="number"
                  v-model.number="customPointCount"
                  :disabled="isRunning"
                  min="3"
                  max="100"
                  class="w-24 bg-white border border-neutral-200 hover:border-neutral-300 focus:border-neutral-900 rounded-lg pl-2.5 pr-8 py-1.5 text-xs font-mono text-neutral-900 focus:outline-none transition shadow-2xs"
                />
                <span class="absolute right-2 text-[11px] text-neutral-400 font-mono pointer-events-none select-none">
                  {{ t('points_suffix').trim() }}
                </span>
              </div>
              <span class="text-[11px] text-neutral-400 font-mono">(3-100)</span>
            </div>

            <!-- Divider if both custom -->
            <div v-if="pointCountPreset === 'custom' && durationPreset === 'custom'" class="hidden sm:block h-4 w-px bg-neutral-200"></div>

            <!-- Custom Settle & Sample Durations -->
            <template v-if="durationPreset === 'custom'">
              <div class="flex items-center space-x-2">
                <span class="text-xs font-medium text-neutral-700">{{ t('settle_duration_label') }}:</span>
                <div class="relative flex items-center">
                  <input
                    type="number"
                    v-model.number="customSettleMs"
                    :disabled="isRunning"
                    step="50"
                    min="50"
                    max="5000"
                    class="w-24 bg-white border border-neutral-200 hover:border-neutral-300 focus:border-neutral-900 rounded-lg pl-2.5 pr-8 py-1.5 text-xs font-mono text-neutral-900 focus:outline-none transition shadow-2xs"
                  />
                  <span class="absolute right-2 text-[11px] text-neutral-400 font-mono pointer-events-none select-none">ms</span>
                </div>
              </div>

              <div class="flex items-center space-x-2">
                <span class="text-xs font-medium text-neutral-700">{{ t('sample_duration_label') }}:</span>
                <div class="relative flex items-center">
                  <input
                    type="number"
                    v-model.number="customSampleMs"
                    :disabled="isRunning"
                    step="50"
                    min="100"
                    max="10000"
                    class="w-24 bg-white border border-neutral-200 hover:border-neutral-300 focus:border-neutral-900 rounded-lg pl-2.5 pr-8 py-1.5 text-xs font-mono text-neutral-900 focus:outline-none transition shadow-2xs"
                  />
                  <span class="absolute right-2 text-[11px] text-neutral-400 font-mono pointer-events-none select-none">ms</span>
                </div>
              </div>
            </template>
          </div>

          <!-- Total Estimated Time Pill -->
          <div class="flex items-center space-x-1.5 bg-white border border-neutral-200/80 px-2.5 py-1 rounded-lg text-xs shadow-2xs ml-auto">
            <Clock class="w-3.5 h-3.5 text-neutral-400 shrink-0" />
            <span class="text-neutral-500">{{ t('estimated_total_time') }}:</span>
            <span class="font-mono font-semibold text-neutral-800">~{{ estimatedDurationSec }}s</span>
            <span class="text-[10px] text-neutral-400 font-mono">({{ settleMs + sampleMs }}ms/点)</span>
          </div>
        </div>
      </transition>
    </div>

    <!-- Error Alert -->
    <div v-if="errorMessage" class="p-3 rounded-lg bg-neutral-100 border border-neutral-300 text-neutral-900 text-xs flex items-center space-x-2">
      <AlertCircle class="w-4 h-4 shrink-0 text-neutral-800" />
      <span>{{ errorMessage }}</span>
    </div>

    <!-- Main Dual-Column Monitoring Section -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <!-- Left Column: Live Screen Viewport with ROI Overlay -->
      <div class="lg:col-span-6 space-y-3">
        <div class="p-4 bg-white border border-neutral-200/80 rounded-xl space-y-3 shadow-xs">
          <div class="flex items-center justify-between border-b border-neutral-100 pb-2.5 flex-wrap gap-2">
            <div class="flex items-center space-x-2.5">
              <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
                <Camera class="w-4 h-4" />
              </div>
              <div>
                <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">
                  {{ t('live_viewport_title') }}
                </h3>
                <p class="text-[11px] text-neutral-400 font-mono">
                  {{ sessionStore.capture ? `${sessionStore.capture.width}×${sessionStore.capture.height} @ ${sessionStore.capture.target_fps}Hz` : t('no_signal_preview') }}
                </p>
              </div>
            </div>
            <div class="flex items-center space-x-2 text-xs">
              <span
                class="w-2 h-2 rounded-full"
                :class="sessionStore.livePreviewUrl ? 'bg-emerald-500' : 'bg-neutral-400'"
              ></span>
              <span class="text-neutral-500 font-mono text-[11px]">
                {{ sessionStore.capture ? `${sessionStore.capture.width}×${sessionStore.capture.height} @ ${sessionStore.capture.target_fps}Hz` : t('no_signal_preview') }}
              </span>
            </div>
          </div>

          <!-- Screen Canvas / Frame Viewport -->
          <div class="aspect-video w-full rounded-lg overflow-hidden bg-neutral-950 border border-neutral-200/80 relative flex items-center justify-center select-none group">
            <template v-if="sessionStore.livePreviewUrl">
              <img
                :src="sessionStore.livePreviewUrl"
                alt="Live Game Preview"
                class="w-full h-full object-contain pointer-events-none"
              />

              <!-- Overlay ROI Bounding Box -->
              <div
                v-if="roiBoxStyle"
                :style="roiBoxStyle"
                class="absolute border-2 border-white bg-white/10 pointer-events-none transition-all duration-75"
              >
                <!-- Corner Anchors -->
                <span class="absolute -top-1 -left-1 w-1.5 h-1.5 bg-white rounded-full"></span>
                <span class="absolute -top-1 -right-1 w-1.5 h-1.5 bg-white rounded-full"></span>
                <span class="absolute -bottom-1 -left-1 w-1.5 h-1.5 bg-white rounded-full"></span>
                <span class="absolute -bottom-1 -right-1 w-1.5 h-1.5 bg-white rounded-full"></span>

                <div class="absolute -top-6 left-0 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-neutral-900 text-white border border-neutral-700 shadow-sm flex items-center space-x-1 whitespace-nowrap">
                  <Crosshair class="w-2.5 h-2.5" />
                  <span>ROI: {{ sessionStore.roi?.width }}×{{ sessionStore.roi?.height }}</span>
                </div>
              </div>
            </template>

            <div v-else class="text-center p-6 space-y-2 text-neutral-500">
              <Camera class="w-7 h-7 mx-auto stroke-1 opacity-50" />
              <p class="text-xs">{{ t('no_signal_preview') }}</p>
              <p class="text-[11px] text-neutral-400">{{ t('frame_not_ready_hint') }}</p>
            </div>
          </div>

          <!-- Viewport Info Footer -->
          <div class="flex items-center justify-between text-xs text-neutral-500 pt-1 font-mono">
            <div class="flex items-center space-x-2">
              <span class="px-2 py-0.5 rounded bg-neutral-100 text-[11px] text-neutral-700">
                {{ t('backend_label') }}: {{ sessionStore.capture?.backend?.toUpperCase() || 'NONE' }}
              </span>
              <span class="text-neutral-300">|</span>
              <span class="text-[11px] text-neutral-500">
                {{ t('occlusion_safe_label') }}: {{ sessionStore.capture?.occlusion_safe ? t('enabled_label') : t('disabled_label') }}
              </span>
            </div>
            <div class="text-right text-neutral-900 font-medium text-[11px]">
              {{ t('stick_push_state') }}: {{ (currentInputValue * 100).toFixed(1) }}% (X+)
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Progress Card & Log Terminal -->
      <div class="lg:col-span-6 space-y-4">
        <!-- Active Progress Card -->
        <div class="p-4 bg-white border border-neutral-200/80 rounded-xl space-y-3 shadow-xs">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2.5">
              <div
                class="w-7 h-7 rounded-lg flex items-center justify-center transition-colors bg-neutral-100 text-neutral-900 shrink-0"
              >
                <Activity class="w-4 h-4" :class="{ 'animate-pulse text-neutral-900': isRunning }" />
              </div>
              <div>
                <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">{{ t('current_progress') }}</h3>
                <p class="text-[11px] text-neutral-400 font-mono">{{ phaseText }}</p>
              </div>
            </div>

            <div class="text-right">
              <div class="text-lg font-bold font-mono text-neutral-900">
                {{ currentPoint }} / {{ totalPoints }}
                <span class="text-xs font-normal text-neutral-400">({{ progressPercent }}%)</span>
              </div>
            </div>
          </div>

          <!-- Progress Bar (Solid Monochrome) -->
          <div class="w-full bg-neutral-100 rounded-full h-1.5 overflow-hidden">
            <div
              class="bg-neutral-900 h-full rounded-full transition-all duration-300"
              :style="{ width: `${progressPercent}%` }"
            ></div>
          </div>

          <div class="flex items-center justify-between text-xs font-mono text-neutral-600 pt-0.5">
            <span>{{ t('stick_input') }}: {{ (currentInputValue * 100).toFixed(1) }}%</span>
            <span class="flex items-center space-x-1.5" :class="isRunning ? 'text-neutral-900 font-medium' : 'text-neutral-400'">
              <Clock v-if="isRunning" class="w-3 h-3 animate-spin" />
              <span>{{ isRunning ? t('running_status') : t('ready_status') }}</span>
            </span>
          </div>
        </div>

        <!-- Terminal-Style Log Console -->
        <div class="p-4 bg-white border border-neutral-200/80 rounded-xl space-y-2.5 relative shadow-xs">
          <!-- Terminal Toolbar -->
          <div class="flex items-center justify-between border-b border-neutral-100 pb-2 flex-wrap gap-2">
            <div class="flex items-center space-x-2.5">
              <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
                <Terminal class="w-4 h-4" />
              </div>
              <div>
                <div class="flex items-center space-x-2">
                  <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">{{ t('measurement_logs') }}</h3>
                  <span class="text-[10px] px-1.5 py-0.2 rounded-full bg-neutral-100 text-neutral-500 font-mono">
                    {{ sessionStore.measurementLogs.length }}
                  </span>
                </div>
                <p class="text-[11px] text-neutral-400 font-mono">
                  {{ isRunning ? t('running_status') : t('ready_status') }}
                </p>
              </div>
            </div>

            <div class="flex items-center space-x-1.5">
              <button
                @click="autoScroll = !autoScroll"
                class="px-2 py-0.5 rounded text-[11px] font-mono transition cursor-pointer border flex items-center space-x-1"
                :class="autoScroll ? 'bg-neutral-900 border-neutral-900 text-white' : 'bg-neutral-100 border-neutral-200 text-neutral-600'"
                :title="t('auto_scroll_btn')"
              >
                <span>{{ t('auto_scroll_btn') }}</span>
                <span class="w-1.5 h-1.5 rounded-full" :class="autoScroll ? 'bg-emerald-400' : 'bg-neutral-400'"></span>
              </button>

              <button
                @click="copyLogs"
                class="p-1 rounded text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100 transition cursor-pointer"
                :title="t('copy_logs')"
              >
                <Check v-if="copied" class="w-3.5 h-3.5 text-neutral-900" />
                <Copy v-else class="w-3.5 h-3.5" />
              </button>

              <button
                @click="sessionStore.clearLogs"
                class="p-1 rounded text-neutral-500 hover:text-rose-600 hover:bg-neutral-100 transition cursor-pointer"
                :title="t('clear_logs')"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- Log Entries Container -->
          <div
            ref="logContainerRef"
            @scroll="onLogScroll"
            class="h-[240px] overflow-y-auto font-mono text-xs p-2.5 space-y-1.5 bg-neutral-950 text-neutral-200 rounded-lg border border-neutral-800 select-text"
          >
            <div
              v-if="sessionStore.measurementLogs.length === 0"
              class="h-full flex items-center justify-center text-neutral-500 text-xs text-center select-none"
            >
              {{ t('click_to_start_log_hint') }}
            </div>

            <div
              v-for="log in sessionStore.measurementLogs"
              :key="log.id"
              class="flex items-start space-x-2 text-[11px] leading-relaxed hover:bg-neutral-900 px-1 py-0.5 rounded transition-colors"
            >
              <span class="text-neutral-500 shrink-0 select-none">[{{ log.timestamp }}]</span>
              <span
                class="px-1.5 py-0.2 rounded text-[9px] shrink-0 uppercase font-medium border"
                :class="getLogLevelClass(log.level)"
              >
                {{ log.level }}
              </span>
              <span class="text-neutral-300 break-all">{{ log.message }}</span>
            </div>
          </div>

          <!-- Floating Return to Bottom Button -->
          <button
            v-if="!autoScroll && sessionStore.measurementLogs.length > 0"
            @click="scrollToBottom"
            class="absolute bottom-6 right-6 bg-neutral-900 hover:bg-neutral-800 text-white text-[11px] px-2.5 py-1 rounded-full shadow border border-neutral-700 flex items-center space-x-1 cursor-pointer transition"
          >
            <ArrowDown class="w-3 h-3" />
            <span>{{ t('scroll_latest') }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Measured Points Real-time Table / Summary -->
    <div v-if="displayPoints && displayPoints.length > 0" class="p-5 bg-white border border-neutral-200/80 rounded-xl space-y-3 shadow-xs">
      <div class="flex items-center justify-between border-b border-neutral-100 pb-3 flex-wrap gap-2">
        <div class="flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
            <CheckCircle2 class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">
              {{ t('sampling_record_title') }}
            </h3>
            <p class="text-[11px] text-neutral-400 font-mono">
              {{ displayPoints.length }} / {{ totalPoints }} {{ t('points_suffix') }}{{ isRunning ? ' · ' + t('realtime_appending') : '' }}
            </p>
          </div>
        </div>
        <span class="text-[11px] text-neutral-400 font-mono">
          {{ isRunning ? t('realtime_appending') : `${t('measurement_completed')}: ${lastResult?.measured_at || t('just_now')}` }}
        </span>
      </div>

      <div class="max-h-64 overflow-y-auto rounded-lg border border-neutral-200">
        <table class="w-full text-left text-xs">
          <thead class="bg-neutral-100 text-neutral-600 sticky top-0">
            <tr>
              <th class="p-2.5">#</th>
              <th class="p-2.5">{{ t('stick_input') }}</th>
              <th class="p-2.5">{{ t('angular_velocity') }}</th>
              <th class="p-2.5">{{ t('normalized_speed') }}</th>
              <th class="p-2.5">{{ t('stability') }}</th>
              <th class="p-2.5">{{ t('coverage') }}</th>
              <th class="p-2.5">{{ t('status') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-neutral-100 font-mono text-neutral-800">
            <tr
              v-for="(pt, idx) in displayPoints"
              :key="idx"
              class="transition-colors hover:bg-neutral-50"
            >
              <td class="p-2.5 text-neutral-400">{{ idx + 1 }}</td>
              <td class="p-2.5 font-bold">{{ (pt.input * 100).toFixed(1) }}%</td>
              <td class="p-2.5 font-medium">
                {{ pt.velocity_px_s !== null ? `${pt.velocity_px_s} px/s` : '-' }}
              </td>
              <td class="p-2.5">
                {{ pt.normalized_speed !== null ? `${(pt.normalized_speed * 100).toFixed(1)}%` : (isRunning ? '...' : '-') }}
              </td>
              <td class="p-2.5">{{ Math.round(pt.stability * 100) }}%</td>
              <td class="p-2.5">{{ Math.round((pt.coverage ?? pt.stability) * 100) }}%</td>
              <td class="p-2.5">
                <span
                  class="px-1.5 py-0.5 rounded text-[10px]"
                  :class="pt.valid ? 'bg-neutral-100 text-neutral-800 border border-neutral-200' : 'bg-rose-50 text-rose-600 border border-rose-200'"
                >
                  {{ pt.valid ? t('status_valid') : t('status_invalid') }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Countdown Modal -->
    <CountdownModal
      v-if="showCountdown"
      @close="showCountdown = false"
      @cancel="cancelMeasurement"
    />
  </div>
</template>
