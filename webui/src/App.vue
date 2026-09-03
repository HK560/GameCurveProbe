<script setup lang="ts">
import { defineAsyncComponent, onMounted, ref } from 'vue'
import { useConnectionStore } from './stores/connection'
import { useSessionStore } from './stores/session'
import { api } from './services/api'
import { initiateApplicationShutdown } from './services/appShutdown'
import { ws } from './services/ws'
import CaptureStep from './components/CaptureStep.vue'
import DeadzoneStep from './components/DeadzoneStep.vue'
import MeasurementStep from './components/MeasurementStep.vue'
const AnalysisStep = defineAsyncComponent(() => import('./components/AnalysisStep.vue'))
import { 
  Monitor, 
  Target, 
  Activity, 
  BarChart3, 
  Gamepad2, 
  Power
} from 'lucide-vue-next'

const connectionStore = useConnectionStore()
const sessionStore = useSessionStore()
const isQuitting = ref(false)

const steps = [
  { id: 1, title: '窗口与抓图', desc: '选择游戏及特征ROI区域', icon: Monitor },
  { id: 2, title: '死区标定', desc: '内外死区交互测定', icon: Target },
  { id: 3, title: '曲线测定', desc: '自动化稳态旋转测定', icon: Activity },
  { id: 4, title: '分析与导出', desc: '拟合曲线与报告下载', icon: BarChart3 },
]

async function quitApplication() {
  if (!window.confirm('确定要退出 GameCurveProbe 吗？当前测定任务将被安全中止。')) {
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

onMounted(async () => {
  await connectionStore.checkHealth()
  sessionStore.initListeners()
  ws.connectEvents()
  ws.connectPreview()
  await sessionStore.loadInitialData()
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
            <p class="text-[11px] text-neutral-400">手柄响应曲线精密测定</p>
          </div>
        </div>

        <div class="flex items-center space-x-3 text-xs">
          <div class="flex items-center space-x-2 px-2.5 py-1 rounded-md bg-neutral-100 text-neutral-600 text-[11px]">
            <span v-if="connectionStore.connected" class="flex items-center text-neutral-700 font-medium">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5"></span>
              服务已连接
            </span>
            <span v-else class="flex items-center text-rose-600 font-medium">
              <span class="w-1.5 h-1.5 rounded-full bg-rose-500 mr-1.5"></span>
              未连接
            </span>
            <span class="text-neutral-300">|</span>
            <span v-if="sessionStore.capture" class="text-neutral-600 font-mono">
              {{ sessionStore.capture.backend.toUpperCase() }} {{ sessionStore.capture.width }}×{{ sessionStore.capture.height }}
            </span>
            <span v-else class="text-neutral-400">
              未抓取窗口
            </span>
          </div>
          <button
            type="button"
            :disabled="isQuitting"
            title="退出并关闭 GameCurveProbe"
            class="flex items-center space-x-1 px-2.5 py-1 rounded-md text-[11px] font-medium text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100 transition disabled:opacity-50 cursor-pointer"
            @click="quitApplication"
          >
            <Power class="w-3.5 h-3.5" />
            <span>{{ isQuitting ? '退出中…' : '退出' }}</span>
          </button>
        </div>
      </div>
    </header>

    <!-- Guided Steps Navigation (Minimalist Segmented) -->
    <div class="border-b border-neutral-200/60 bg-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6">
        <nav class="flex space-x-1 sm:space-x-2 py-2">
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
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
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
  </div>
</template>
