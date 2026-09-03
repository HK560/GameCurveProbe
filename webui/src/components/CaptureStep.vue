<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useSessionStore } from '../stores/session'
import RoiSelector from './RoiSelector.vue'
import QualityBadge from './QualityBadge.vue'
import { RefreshCw, Play, ArrowRight, Settings2, ShieldAlert } from 'lucide-vue-next'
import type { RoiRect } from '../types/api'
import { captureErrorMessage, captureModeInfo, type CaptureMode } from '../services/captureModes'

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
    errorMessage.value = '请先在列表中选择目标窗口'
    return
  }
  errorMessage.value = null
  try {
    await sessionStore.attachCapture(selectedWindowId.value, selectedBackend.value, selectedFps.value)
  } catch (err: any) {
    errorMessage.value = captureErrorMessage(err)
  }
}

async function onRoiChange(newRoi: RoiRect) {
  try {
    await sessionStore.updateRoi(newRoi)
  } catch (err: any) {
    console.error('Failed to update ROI:', err)
  }
}

function proceedToDeadzone() {
  sessionStore.activeStep = 2
}
</script>

<template>
  <div class="space-y-6">
    <!-- Top Control Bar -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 items-end bg-slate-900/80 p-4 rounded-xl border border-slate-800">
      <!-- Window Selector -->
      <div class="lg:col-span-5 space-y-1.5">
        <div class="flex items-center justify-between">
          <label class="text-xs font-semibold text-slate-300">目标游戏窗口</label>
          <button
            @click="refreshWindows"
            class="text-[11px] text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 cursor-pointer"
          >
            <RefreshCw class="w-3 h-3" />
            <span>刷新窗口列表</span>
          </button>
        </div>
        <select
          v-model="selectedWindowId"
          class="w-full bg-slate-800/90 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition"
        >
          <option :value="null" disabled>-- 请选择运行中的游戏窗口 --</option>
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
        <label class="text-xs font-semibold text-slate-300">抓图引擎</label>
        <select
          v-model="selectedBackend"
          class="w-full bg-slate-800/90 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition"
        >
          <option value="auto">Auto（WGC 独立窗口捕获）</option>
          <option value="wgc">Windows Graphics Capture（WGC）</option>
          <option value="dxcam">屏幕区域兼容模式（DXGI）</option>
        </select>
      </div>

      <!-- Target FPS -->
      <div class="lg:col-span-2 space-y-1.5">
        <label class="text-xs font-semibold text-slate-300">目标帧率</label>
        <select
          v-model="selectedFps"
          class="w-full bg-slate-800/90 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition"
        >
          <option :value="60">60 FPS</option>
          <option :value="120">120 FPS (推荐)</option>
          <option :value="240">240 FPS (高刷)</option>
        </select>
      </div>

      <!-- Action Button -->
      <div class="lg:col-span-2">
        <button
          type="button"
          @click="handleAttach"
          :disabled="!selectedWindowId || sessionStore.isAttaching"
          class="w-full bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold py-2 px-4 rounded-lg shadow-md shadow-indigo-600/30 flex items-center justify-center space-x-2 transition cursor-pointer"
        >
          <RefreshCw v-if="sessionStore.isAttaching" class="w-4 h-4 animate-spin" />
          <Play v-else class="w-4 h-4 fill-current" />
          <span>{{ isAttached ? '重新绑定' : '开始抓图' }}</span>
        </button>
      </div>
    </div>

    <div
      v-if="modeInfo.warning"
      class="p-3.5 rounded-xl bg-amber-950/50 border border-amber-500/50 text-amber-200 text-xs flex items-center space-x-2"
    >
      <ShieldAlert class="w-4 h-4 shrink-0 text-amber-400" />
      <span>{{ modeInfo.warning }}</span>
    </div>

    <!-- Error Alert -->
    <div v-if="errorMessage || healthErrorMessage" class="p-3.5 rounded-xl bg-rose-950/60 border border-rose-500/50 text-rose-300 text-xs flex items-center space-x-2">
      <ShieldAlert class="w-4 h-4 shrink-0 text-rose-400" />
      <span>{{ errorMessage || healthErrorMessage }}</span>
    </div>

    <!-- Main Viewport and ROI Assessment Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Left: Interactive Canvas / Viewport -->
      <div class="lg:col-span-8 space-y-3">
        <div class="flex items-center justify-between text-xs text-slate-400">
          <span class="flex items-center space-x-1.5">
            <span class="w-2 h-2 rounded-full" :class="isAttached ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'"></span>
            <span>{{ isAttached ? `已连接: ${captureInfo?.width}×${captureInfo?.height} @ ${captureInfo?.target_fps}Hz` : '画面未就绪' }}</span>
          </span>
          <span class="text-slate-500">提示: 鼠标左键在画面中拖拽画框选取</span>
        </div>

        <RoiSelector
          :image-url="sessionStore.livePreviewUrl"
          :image-width="sessionStore.capture?.width || 1920"
          :image-height="sessionStore.capture?.height || 1080"
          :current-roi="sessionStore.roi"
          @update:roi="onRoiChange"
        />
      </div>

      <!-- Right: ROI Diagnostics and Quality Score -->
      <div class="lg:col-span-4 space-y-4 flex flex-col justify-between">
        <div class="space-y-4">
          <div class="flex items-center space-x-2 text-sm font-semibold text-slate-200">
            <Settings2 class="w-4 h-4 text-indigo-400" />
            <span>特征分析 (ROI 质量)</span>
          </div>

          <!-- Quality Badge and Progress -->
          <QualityBadge :quality="roiQuality" />

          <!-- Coordinate Display -->
          <div v-if="sessionStore.roi" class="p-3.5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-2">
            <div class="text-xs font-semibold text-slate-300">选区坐标信息</div>
            <div class="grid grid-cols-2 gap-2 text-xs font-mono text-slate-300">
              <div class="bg-slate-800/80 px-2.5 py-1.5 rounded border border-slate-700/60">
                <span class="text-slate-500">X:</span> {{ sessionStore.roi.x }} px
              </div>
              <div class="bg-slate-800/80 px-2.5 py-1.5 rounded border border-slate-700/60">
                <span class="text-slate-500">Y:</span> {{ sessionStore.roi.y }} px
              </div>
              <div class="bg-slate-800/80 px-2.5 py-1.5 rounded border border-slate-700/60">
                <span class="text-slate-500">宽:</span> {{ sessionStore.roi.width }} px
              </div>
              <div class="bg-slate-800/80 px-2.5 py-1.5 rounded border border-slate-700/60">
                <span class="text-slate-500">高:</span> {{ sessionStore.roi.height }} px
              </div>
            </div>
          </div>
        </div>

        <!-- Next Step Button -->
        <div class="pt-4 border-t border-slate-800">
          <button
            @click="proceedToDeadzone"
            :disabled="!isAttached || !sessionStore.roi || (roiQuality ? roiQuality.score < 25 : false)"
            class="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold py-2.5 px-4 rounded-xl shadow-lg shadow-indigo-600/30 flex items-center justify-center space-x-2 transition cursor-pointer"
          >
            <span>下一步：手柄死区标定</span>
            <ArrowRight class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
