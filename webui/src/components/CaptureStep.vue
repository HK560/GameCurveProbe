<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useSessionStore } from '../stores/session'
import RoiSelector from './RoiSelector.vue'
import QualityBadge from './QualityBadge.vue'
import { RefreshCw, Play, Settings2, ShieldAlert, Monitor } from 'lucide-vue-next'
import type { RoiRect } from '../types/api'
import { captureErrorMessage, captureModeInfo, type CaptureMode } from '../services/captureModes'
import { t } from '../services/i18n'

const sessionStore = useSessionStore()

const selectedWindowId = ref<number | null>(null)
const selectedBackend = ref<CaptureMode>('auto')
const selectedFps = ref<number>(120)
const errorMessage = ref<string | null>(null)

const isAttached = computed(() => !!sessionStore.capture)
const captureInfo = computed(() => sessionStore.capture)
const roiQuality = computed(() => sessionStore.roiQuality)
const modeInfo = computed(() => captureModeInfo(selectedBackend.value))
const healthErrorMessage = computed(() => {
  const code = sessionStore.captureHealth?.last_error
  return code ? captureErrorMessage({ code }) : null
})
let healthTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  healthTimer = setInterval(() => {
    if (sessionStore.capture) {
      sessionStore.refreshCaptureHealth().catch(() => undefined)
    }
  }, 500)
})

onUnmounted(() => {
  if (healthTimer !== null) clearInterval(healthTimer)
})

watch(
  () => sessionStore.capture,
  (cap) => {
    if (cap?.window_id) {
      selectedWindowId.value = cap.window_id
    }
  },
  { immediate: true }
)

async function refreshWindows() {
  errorMessage.value = null
  await sessionStore.fetchWindows()
}

async function handleAttach() {
  if (!selectedWindowId.value) {
    errorMessage.value = t('select_window_first')
    return
  }
  errorMessage.value = null
  try {
    await sessionStore.attachCapture(selectedWindowId.value, selectedBackend.value, selectedFps.value)
  } catch (err: any) {
    errorMessage.value = captureErrorMessage(err)
  }
}

async function onWindowSelect() {
  if (selectedWindowId.value) {
    await handleAttach()
  }
}

async function onBackendOrFpsChange() {
  if (selectedWindowId.value && isAttached.value) {
    await handleAttach()
  }
}

async function onRoiChange(newRoi: RoiRect) {
  try {
    await sessionStore.updateRoi(newRoi)
  } catch (err: any) {
    console.error('Failed to update ROI:', err)
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Top Control Bar -->
    <div class="bg-white p-4 rounded-xl border border-neutral-200/80 shadow-xs space-y-3">
      <div class="flex items-center justify-between border-b border-neutral-100 pb-3 flex-wrap gap-2">
        <div class="flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
            <Monitor class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">
              {{ t('target_window') }} &amp; {{ t('capture_engine') }}
            </h3>
            <p class="text-[11px] text-neutral-400">
              {{ t('select_window_signal_hint') }}
            </p>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 items-end">
        <!-- Window Selector -->
        <div class="lg:col-span-5 space-y-1.5">
          <div class="flex items-center justify-between">
            <label class="text-xs font-medium text-neutral-700">{{ t('target_window') }}</label>
            <button
              @click="refreshWindows"
              class="text-[11px] text-neutral-500 hover:text-neutral-900 flex items-center space-x-1 cursor-pointer transition"
            >
              <RefreshCw class="w-3 h-3" />
              <span>{{ t('refresh_list') }}</span>
            </button>
          </div>
        <select
          v-model="selectedWindowId"
          @change="onWindowSelect"
          class="w-full bg-neutral-50 hover:bg-white focus:bg-white border border-neutral-200 rounded-lg px-3 py-2 text-sm text-neutral-900 focus:outline-none focus:border-neutral-900 transition"
        >
          <option :value="null" disabled>{{ t('select_window_placeholder') }}</option>
          <option
            v-for="win in sessionStore.windows"
            :key="win.id"
            :value="win.id"
          >
            {{ win.title || `HWND ${win.id}` }} ({{ win.width }}×{{ win.height }})
          </option>
        </select>
      </div>

      <!-- Backend Selector -->
      <div class="lg:col-span-3 space-y-1.5">
        <label class="text-xs font-medium text-neutral-700">{{ t('capture_engine') }}</label>
        <select
          v-model="selectedBackend"
          @change="onBackendOrFpsChange"
          class="w-full bg-neutral-50 hover:bg-white focus:bg-white border border-neutral-200 rounded-lg px-3 py-2 text-sm text-neutral-900 focus:outline-none focus:border-neutral-900 transition"
        >
          <option value="auto">{{ t('wgc_desc') }}</option>
          <option value="wgc">Windows Graphics Capture（WGC）</option>
          <option value="dxcam">{{ t('dxcam_desc') }}</option>
        </select>
      </div>

      <!-- Target FPS -->
      <div class="lg:col-span-2 space-y-1.5">
        <label class="text-xs font-medium text-neutral-700">{{ t('target_fps') }}</label>
        <select
          v-model="selectedFps"
          @change="onBackendOrFpsChange"
          class="w-full bg-neutral-50 hover:bg-white focus:bg-white border border-neutral-200 rounded-lg px-3 py-2 text-sm text-neutral-900 focus:outline-none focus:border-neutral-900 transition"
        >
          <option :value="60">60 FPS</option>
          <option :value="120">120 FPS ({{ t('recommended') }})</option>
          <option :value="240">240 FPS ({{ t('high_refresh') }})</option>
        </select>
      </div>

      <!-- Action Button -->
      <div class="lg:col-span-2">
        <button
          type="button"
          @click="handleAttach"
          :disabled="!selectedWindowId || sessionStore.isAttaching"
          class="w-full bg-neutral-900 hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium py-2 px-4 rounded-lg flex items-center justify-center space-x-2 transition cursor-pointer"
        >
          <RefreshCw v-if="sessionStore.isAttaching" class="w-4 h-4 animate-spin" />
          <Play v-else class="w-3.5 h-3.5 fill-current" />
          <span>{{ isAttached ? t('rebind') : t('start_capture') }}</span>
        </button>
      </div>
    </div>
  </div>

    <div
      v-if="modeInfo.warning"
      class="p-3 rounded-lg bg-neutral-100 border border-neutral-200 text-neutral-700 text-xs flex items-center space-x-2"
    >
      <ShieldAlert class="w-4 h-4 shrink-0 text-neutral-600" />
      <span>{{ modeInfo.warning }}</span>
    </div>

    <!-- Error Alert -->
    <div v-if="errorMessage || healthErrorMessage" class="p-3 rounded-lg bg-neutral-100 border border-neutral-300 text-neutral-900 text-xs flex items-center space-x-2">
      <ShieldAlert class="w-4 h-4 shrink-0 text-neutral-800" />
      <span>{{ errorMessage || healthErrorMessage }}</span>
    </div>

    <!-- Main Viewport and ROI Assessment Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <!-- Left: Interactive Canvas / Viewport -->
      <div class="lg:col-span-8 space-y-2">
        <div class="flex items-center justify-between text-xs text-neutral-500">
          <span class="flex items-center space-x-1.5">
            <span class="w-2 h-2 rounded-full" :class="isAttached ? 'bg-emerald-500' : 'bg-neutral-400'"></span>
            <span class="font-mono text-neutral-700">{{ isAttached ? `${t('connected_status_label')}: ${captureInfo?.width}×${captureInfo?.height} @ ${captureInfo?.target_fps}Hz` : t('no_signal_preview') }}</span>
          </span>
          <span class="text-neutral-400">{{ t('roi_instruction') }}</span>
        </div>

        <RoiSelector
          :image-url="sessionStore.livePreviewUrl"
          :image-width="sessionStore.capture?.width || 1920"
          :image-height="sessionStore.capture?.height || 1080"
          :current-roi="sessionStore.roi"
          @update:roi="onRoiChange"
        />
      </div>

      <!-- Right: ROI Diagnostics and Quality Score Card -->
      <div class="lg:col-span-4 bg-white border border-neutral-200/80 rounded-xl p-4 shadow-xs space-y-4">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div class="flex items-center space-x-2.5">
            <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
              <Settings2 class="w-4 h-4" />
            </div>
            <div>
              <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">
                {{ t('captured_frame_roi') }}
              </h3>
              <p class="text-[11px] text-neutral-400">
                {{ t('roi_instruction') }}
              </p>
            </div>
          </div>
        </div>

        <!-- Quality Badge and Progress -->
        <QualityBadge :quality="roiQuality" />

        <!-- Coordinate Display -->
        <div v-if="sessionStore.roi" class="p-3 bg-neutral-50 rounded-lg border border-neutral-200/60 space-y-2">
          <div class="text-[11px] font-semibold uppercase tracking-wider text-neutral-700">{{ t('roi_size_info') }}</div>
          <div class="grid grid-cols-2 gap-2 text-xs font-mono text-neutral-600">
            <div class="bg-white px-2.5 py-1.5 rounded border border-neutral-200/60 shadow-2xs">
              <span class="text-neutral-400">X:</span> {{ sessionStore.roi.x }} px
            </div>
            <div class="bg-white px-2.5 py-1.5 rounded border border-neutral-200/60 shadow-2xs">
              <span class="text-neutral-400">Y:</span> {{ sessionStore.roi.y }} px
            </div>
            <div class="bg-white px-2.5 py-1.5 rounded border border-neutral-200/60 shadow-2xs">
              <span class="text-neutral-400">{{ t('width_label') }}:</span> {{ sessionStore.roi.width }} px
            </div>
            <div class="bg-white px-2.5 py-1.5 rounded border border-neutral-200/60 shadow-2xs">
              <span class="text-neutral-400">{{ t('height_label') }}:</span> {{ sessionStore.roi.height }} px
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
