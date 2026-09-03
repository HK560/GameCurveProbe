<script setup lang="ts">
import { onMounted } from 'vue'
import { useConnectionStore } from './stores/connection'
import { useSessionStore } from './stores/session'
import { ws } from './services/ws'
import { 
  Monitor, 
  Target, 
  Activity, 
  BarChart3, 
  Gamepad2, 
  Wifi, 
  WifiOff 
} from 'lucide-vue-next'

const connectionStore = useConnectionStore()
const sessionStore = useSessionStore()

const steps = [
  { id: 1, title: '窗口与抓图', desc: '选择游戏及特征ROI区域', icon: Monitor },
  { id: 2, title: '死区标定', desc: '内外死区交互测定', icon: Target },
  { id: 3, title: '曲线测定', desc: '自动化稳态旋转测定', icon: Activity },
  { id: 4, title: '分析与导出', desc: '拟合曲线与报告下载', icon: BarChart3 },
]

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
          <h2 class="text-xl font-semibold text-white mb-2">步骤 1: 窗口与抓图配置</h2>
          <p class="text-sm text-slate-400 mb-6">选择目标游戏窗口，系统将自动绑定 Windows 现代图形捕获（WGC），并在游戏画面中圈选高对比度特征区域。</p>
        </div>
        <div v-else-if="sessionStore.activeStep === 2">
          <h2 class="text-xl font-semibold text-white mb-2">步骤 2: 手柄内外死区标定</h2>
          <p class="text-sm text-slate-400 mb-6">通过微调步进输出实时探测画面微动点，准确测定物理死区与游戏软件内死区。</p>
        </div>
        <div v-else-if="sessionStore.activeStep === 3">
          <h2 class="text-xl font-semibold text-white mb-2">步骤 3: 响应曲线全自动测定</h2>
          <p class="text-sm text-slate-400 mb-6">执行稳态角速度测定任务，系统将按预设步长遍历各采样点并实时统计角速度。</p>
        </div>
        <div v-else-if="sessionStore.activeStep === 4">
          <h2 class="text-xl font-semibold text-white mb-2">步骤 4: 曲线拟合分析与报告导出</h2>
          <p class="text-sm text-slate-400 mb-6">可视化查看响应曲线、曲率分段及分类模型，支持导出为标准化 JSON 及 CSV 格式。</p>
        </div>
      </div>
    </main>
  </div>
</template>
