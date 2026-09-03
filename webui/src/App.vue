<script setup lang="ts">
import { defineAsyncComponent, onMounted, onUnmounted, ref } from 'vue'
import { useConnectionStore } from './stores/connection'
import { useSessionStore } from './stores/session'
import { api } from './services/api'
import { initiateApplicationShutdown } from './services/appShutdown'
import { soundSynth } from './services/sound'
import { ws } from './services/ws'
import CaptureStep from './components/CaptureStep.vue'
import DeadzoneStep from './components/DeadzoneStep.vue'
import MeasurementStep from './components/MeasurementStep.vue'
import HotkeySettingsModal from './components/HotkeySettingsModal.vue'
const AnalysisStep = defineAsyncComponent(() => import('./components/AnalysisStep.vue'))
import { 
  Monitor, 
  Target, 
  Activity, 
  BarChart3, 
  Gamepad2, 
  Power,
  Keyboard
} from 'lucide-vue-next'

const connectionStore = useConnectionStore()
const sessionStore = useSessionStore()
const isQuitting = ref(false)
const wakeInput = ref('right_stick')
const isWaking = ref(false)
const showHotkeyModal = ref(false)

async function toggleController() {
  try {
    await connectionStore.setControllerEnabled(!connectionStore.controllerEnabled)
  } catch (err: any) {
    window.alert(err.message || 'ViGEmBus 手柄状态切换失败')
  }
}

async function wakeGame() {
  isWaking.value = true
  try {
    await api.wakeController(wakeInput.value)
    window.setTimeout(() => { isWaking.value = false }, 500)
  } catch (err: any) {
    isWaking.value = false
    window.alert(err.message || '手柄唤醒失败')
  }
}

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

function handleKeyDown(event: KeyboardEvent) {
  // Ignore hotkey triggers when user is typing in an input/textarea/select
  const target = event.target as HTMLElement | null
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT')) {
    return
  }

  const cfg = sessionStore.config
  if (!cfg || cfg.hotkey_enabled === false) return

  const startKey = (cfg.hotkey_start || 'F9').toUpperCase()
  const stopKey = (cfg.hotkey_stop || 'F10').toUpperCase()

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
  }
}

onMounted(async () => {
  await connectionStore.checkHealth()
  sessionStore.initListeners()
  ws.connectEvents()
  ws.connectPreview()
  await sessionStore.loadInitialData()
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

          <!-- Hotkey & Sound settings button -->
          <button
            type="button"
            class="flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 transition cursor-pointer border border-neutral-200/80"
            title="设置快捷键与操作提示音效"
            @click="showHotkeyModal = true"
          >
            <Keyboard class="w-3.5 h-3.5 text-neutral-700" />
            <span>快捷键 & 音效</span>
            <span class="font-mono text-[10px] bg-neutral-100 px-1 py-0.2 rounded text-neutral-500">
              {{ sessionStore.config?.hotkey_start || 'F9' }} / {{ sessionStore.config?.hotkey_stop || 'F10' }}
            </span>
          </button>

          <label
            class="flex items-center gap-2 px-2.5 py-1 rounded-md text-[11px] font-medium text-neutral-600 hover:bg-neutral-100 cursor-pointer"
            :class="{ 'opacity-50 cursor-wait': connectionStore.isUpdatingController }"
            title="启用或关闭 ViGEmBus 虚拟手柄"
          >
            <span>ViGEmBus</span>
            <input
              type="checkbox"
              class="sr-only peer"
              :checked="connectionStore.controllerEnabled"
              :disabled="connectionStore.isUpdatingController || !connectionStore.controllerReady"
              aria-label="ViGEmBus 虚拟手柄开关"
              @change="toggleController"
            />
            <span class="relative w-7 h-4 rounded-full bg-neutral-300 peer-checked:bg-emerald-500 transition-colors after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:w-3 after:h-3 after:rounded-full after:bg-white after:transition-transform peer-checked:after:translate-x-3"></span>
          </label>
          <div class="flex items-center gap-1.5">
            <select
              v-model="wakeInput"
              :disabled="isWaking || !connectionStore.controllerEnabled"
              aria-label="选择唤醒按键"
              class="h-7 rounded-md border border-neutral-200 bg-white px-2 text-[11px] text-neutral-600 disabled:opacity-50"
            >
              <option value="right_stick">RS（右摇杆按下）</option>
              <option value="x">X</option>
              <option value="y">Y</option>
              <option value="a">A</option>
              <option value="b">B</option>
              <option value="left_bumper">LB</option>
              <option value="right_bumper">RB</option>
              <option value="left_trigger">LT</option>
              <option value="right_trigger">RT</option>
            </select>
            <button
              type="button"
              :disabled="isWaking || !connectionStore.controllerEnabled"
              class="h-7 rounded-md bg-neutral-900 px-2.5 text-[11px] font-medium text-white hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50"
              title="按下所选按键 0.5 秒"
              @click="wakeGame"
            >
              {{ isWaking ? '按下中…' : '唤醒游戏' }}
            </button>
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

    <!-- Hotkey & Sound Settings Modal -->
    <HotkeySettingsModal
      :show="showHotkeyModal"
      @close="showHotkeyModal = false"
    />
  </div>
</template>
