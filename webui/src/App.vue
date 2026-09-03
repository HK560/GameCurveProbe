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
  Wifi, 
  WifiOff,
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
  <div class="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
    <!-- Top Navigation Bar -->
    <header class="border-b border-slate-800/80 bg-slate-900/50 backdrop-blur sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Gamepad2 class="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 class="text-lg font-bold bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
              GameCurveProbe
            </h1>
            <p class="text-xs text-slate-400">游戏手柄响应曲线精密测定仪 2.0</p>
          </div>
        </div>

        <div class="flex items-center space-x-4 text-sm">
          <div class="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-slate-800/70 border border-slate-700/60 text-xs">
            <span v-if="connectionStore.connected" class="flex items-center text-emerald-400">
              <Wifi class="w-3.5 h-3.5 mr-1.5 animate-pulse" />
              本地服务已连接
            </span>
            <span v-else class="flex items-center text-rose-400">
              <WifiOff class="w-3.5 h-3.5 mr-1.5" />
              服务未连接
            </span>
            <span class="text-slate-500">|</span>
            <span v-if="sessionStore.capture" class="text-slate-300">
              {{ sessionStore.capture.backend.toUpperCase() }} {{ sessionStore.capture.width }}×{{ sessionStore.capture.height }}
            </span>
            <span v-else class="text-slate-500">
              未抓取窗口
            </span>
          </div>
          <button
            type="button"
            :disabled="isQuitting"
            title="退出并关闭 GameCurveProbe"
            class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-rose-700/60 bg-rose-950/40 text-xs font-semibold text-rose-300 transition hover:bg-rose-900/60 hover:text-rose-100 disabled:cursor-wait disabled:opacity-60"
            @click="quitApplication"
          >
            <Power class="w-3.5 h-3.5" />
            <span>{{ isQuitting ? '正在退出…' : '退出程序' }}</span>
          </button>
        </div>
      </div>
    </header>

    <!-- Guided Steps Ribbon -->
    <div class="border-b border-slate-800/60 bg-slate-900/30">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 py-4">
        <nav class="grid grid-cols-4 gap-2 sm:gap-4">
          <button
            v-for="step in steps"
            :key="step.id"
            @click="sessionStore.activeStep = step.id"
            class="flex items-center space-x-3 p-3 rounded-xl border text-left transition-all duration-200 cursor-pointer"
            :class="[
              sessionStore.activeStep === step.id
                ? 'bg-indigo-600/15 border-indigo-500/50 shadow-sm shadow-indigo-500/10'
                : 'bg-slate-900/40 border-slate-800/50 hover:bg-slate-800/40 hover:border-slate-700/60'
            ]"
          >
            <div
              class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
              :class="[
                sessionStore.activeStep === step.id
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/30'
                  : 'bg-slate-800 text-slate-400'
              ]"
            >
              <component :is="step.icon" class="w-4 h-4" />
            </div>
            <div class="min-w-0 hidden sm:block">
              <div class="text-xs font-semibold" :class="sessionStore.activeStep === step.id ? 'text-indigo-400' : 'text-slate-300'">
                第 {{ step.id }} 步
              </div>
              <div class="text-sm font-medium text-slate-100 truncate">
                {{ step.title }}
              </div>
            </div>
          </button>
        </nav>
      </div>
    </div>

    <!-- Main Content Container -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6">
      <div class="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 shadow-xl backdrop-blur-sm">
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
      </div>
    </main>
  </div>
</template>
