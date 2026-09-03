<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useSessionStore } from '../stores/session'
import { 
  Activity, 
  Play, 
  Square, 
  ArrowLeft, 
  ArrowRight, 
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

const sessionStore = useSessionStore()

const rangeMode = ref<RangeMode>(sessionStore.config?.range_mode || 'full')
const pointCount = ref<number>(sessionStore.config?.point_count || 17)
const errorMessage = ref<string | null>(null)

const logContainerRef = ref<HTMLElement | null>(null)
const autoScroll = ref(true)
const copied = ref(false)

const activeJob = computed(() => sessionStore.activeJob)
const isRunning = computed(() => activeJob.value?.state === 'running' || activeJob.value?.state === 'queued')
const progressData = computed(() => activeJob.value?.progress)
const currentPoint = computed(() => progressData.value?.current_point || 0)
const totalPoints = computed(() => progressData.value?.total_points || pointCount.value)
const progressPercent = computed(() => {
  if (!totalPoints.value || totalPoints.value === 0) return 0
  return Math.round((currentPoint.value / totalPoints.value) * 100)
})

const lastResult = computed(() => sessionStore.lastResult)
const hasCompleted = computed(() => !!lastResult.value && !isRunning.value)

const currentPhase = computed(() => progressData.value?.phase || (isRunning.value ? 'running' : 'idle'))
const phaseText = computed(() => {
  switch (currentPhase.value) {
    case 'stage_start': return '测定启动准备'
    case 'point_settle': return '摇杆推杆·等待稳定'
    case 'point_sampling': return '特征追踪·光流采样'
    case 'point_retry': return '失稳自动复测中'
    case 'point_done': return '单点采样就绪'
    case 'stage_completed': return '全流程完成·数据分析中'
    default: return isRunning.value ? '稳态测定进行中' : '等待启动'
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
    console.warn('Failed to copy logs:', err)
  }
}

function getLogLevelClass(level: string) {
  switch (level) {
    case 'action': return 'bg-indigo-950/80 text-indigo-300 border-indigo-700/60'
    case 'settle': return 'bg-amber-950/80 text-amber-300 border-amber-700/60'
    case 'sampling': return 'bg-cyan-950/80 text-cyan-300 border-cyan-700/60'
    case 'warn': return 'bg-amber-900/80 text-amber-200 border-amber-600/70'
    case 'success': return 'bg-emerald-950/80 text-emerald-300 border-emerald-700/60'
    case 'error': return 'bg-rose-950/80 text-rose-300 border-rose-700/60'
    default: return 'bg-slate-800 text-slate-300 border-slate-700'
  }
}

async function applyConfig() {
  await sessionStore.updateConfig({
    range_mode: rangeMode.value,
    point_count: pointCount.value,
  })
}

async function startMeasurement() {
  errorMessage.value = null
  try {
    await applyConfig()
    await sessionStore.startMeasurement(rangeMode.value)
  } catch (err: any) {
    errorMessage.value = err.message || '启动测定失败，请确认手柄驱动已就绪'
  }
}

async function cancelMeasurement() {
  if (activeJob.value?.id) {
    await sessionStore.cancelJob(activeJob.value.id)
  }
}

function goBack() {
  sessionStore.activeStep = 2
}

function proceedToAnalysis() {
  sessionStore.activeStep = 4
}
</script>

<template>
  <div class="space-y-6">
    <!-- Config Bar -->
    <div class="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-4 shadow-sm">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center space-x-2">
          <Sliders class="w-4 h-4 text-indigo-400" />
          <span class="text-sm font-semibold text-white">采样参数配置</span>
        </div>
        <div class="text-xs text-slate-400">
          基于当前死区: 内死区 {{ ((sessionStore.config?.inner_deadzone || 0) * 100).toFixed(1) }}%, 
          外死区 {{ ((sessionStore.config?.outer_deadzone || 1) * 100).toFixed(1) }}%
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-300">测定范围模式</label>
          <select
            v-model="rangeMode"
            :disabled="isRunning"
            class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition disabled:opacity-50"
          >
            <option value="full">全范围 (内死区至外死区)</option>
            <option value="active_range">有效行程（内死区至外死区）</option>
          </select>
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-300">采样点密度</label>
          <select
            v-model.number="pointCount"
            :disabled="isRunning"
            class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition disabled:opacity-50"
          >
            <option :value="9">9 点 (快速摸底, ~15秒)</option>
            <option :value="17">17 点 (标准推荐, ~30秒)</option>
            <option :value="33">33 点 (高精密度, ~60秒)</option>
          </select>
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-300">单点稳定/采样时长</label>
          <div class="px-3 py-2 bg-slate-800/60 border border-slate-700/60 rounded-lg text-xs font-mono text-slate-300 flex items-center justify-between">
            <span>Settle: {{ sessionStore.config?.settle_ms }}ms</span>
            <span>Sample: {{ sessionStore.config?.sample_ms }}ms</span>
          </div>
        </div>

        <div>
          <button
            v-if="!isRunning"
            @click="startMeasurement"
            class="w-full bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-semibold py-2 px-4 rounded-lg shadow-md shadow-indigo-600/30 flex items-center justify-center space-x-2 transition cursor-pointer"
          >
            <Play class="w-4 h-4 fill-current" />
            <span>开始稳态测定</span>
          </button>
          <button
            v-else
            @click="cancelMeasurement"
            class="w-full bg-rose-600 hover:bg-rose-500 text-white font-semibold py-2 px-4 rounded-lg shadow-md shadow-rose-600/30 flex items-center justify-center space-x-2 transition cursor-pointer"
          >
            <Square class="w-4 h-4 fill-current" />
            <span>中止当前任务</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Error Alert -->
    <div v-if="errorMessage" class="p-3.5 rounded-xl bg-rose-950/60 border border-rose-500/50 text-rose-300 text-xs flex items-center space-x-2">
      <AlertCircle class="w-4 h-4 shrink-0 text-rose-400" />
      <span>{{ errorMessage }}</span>
    </div>

    <!-- Main Dual-Column Monitoring Section -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <!-- Left Column: Live Screen Viewport with ROI Overlay -->
      <div class="lg:col-span-6 space-y-3">
        <div class="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-3">
          <div class="flex items-center justify-between border-b border-slate-800 pb-2.5">
            <div class="flex items-center space-x-2">
              <Camera class="w-4 h-4 text-indigo-400" />
              <span class="text-sm font-semibold text-white">实时画面与追踪监控</span>
            </div>
            <div class="flex items-center space-x-2 text-xs">
              <span
                class="w-2 h-2 rounded-full"
                :class="sessionStore.livePreviewUrl ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'"
              ></span>
              <span class="text-slate-400 font-mono">
                {{ sessionStore.capture ? `${sessionStore.capture.width}×${sessionStore.capture.height} @ ${sessionStore.capture.target_fps}Hz` : '画面未就绪' }}
              </span>
            </div>
          </div>

          <!-- Screen Canvas / Frame Viewport -->
          <div class="aspect-video w-full rounded-xl overflow-hidden bg-slate-950 border border-slate-800 relative flex items-center justify-center select-none group">
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
                class="absolute border-2 border-indigo-400 bg-indigo-500/15 shadow-[0_0_15px_rgba(99,102,241,0.35)] pointer-events-none transition-all duration-75"
              >
                <!-- Corner Anchors -->
                <span class="absolute -top-1 -left-1 w-2 h-2 border-t-2 border-l-2 border-white"></span>
                <span class="absolute -top-1 -right-1 w-2 h-2 border-t-2 border-r-2 border-white"></span>
                <span class="absolute -bottom-1 -left-1 w-2 h-2 border-b-2 border-l-2 border-white"></span>
                <span class="absolute -bottom-1 -right-1 w-2 h-2 border-b-2 border-r-2 border-white"></span>

                <div class="absolute -top-6 left-0 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-indigo-900/90 text-indigo-200 border border-indigo-700 shadow flex items-center space-x-1 whitespace-nowrap">
                  <Crosshair class="w-2.5 h-2.5" />
                  <span>追踪ROI: {{ sessionStore.roi?.width }}×{{ sessionStore.roi?.height }}</span>
                </div>
              </div>
            </template>

            <div v-else class="text-center p-6 space-y-2 text-slate-500">
              <Camera class="w-8 h-8 mx-auto stroke-1 opacity-60" />
              <p class="text-xs">暂未获取到实时画面</p>
              <p class="text-[11px] text-slate-600">请先在「窗口与抓图」步骤绑定游戏窗口</p>
            </div>
          </div>

          <!-- Viewport Info Footer -->
          <div class="flex items-center justify-between text-xs text-slate-400 pt-1 font-mono">
            <div class="flex items-center space-x-2">
              <span class="px-2 py-0.5 rounded bg-slate-800 text-[11px] text-slate-300">
                后端: {{ sessionStore.capture?.backend?.toUpperCase() || 'NONE' }}
              </span>
              <span class="text-slate-500">|</span>
              <span class="text-[11px] text-slate-400">
                安全遮挡防护: {{ sessionStore.capture?.occlusion_safe ? '开启' : '关闭' }}
              </span>
            </div>
            <div class="text-right text-indigo-300 text-[11px]">
              推杆状态: {{ (currentInputValue * 100).toFixed(1) }}% (X+)
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Progress Card & Log Terminal -->
      <div class="lg:col-span-6 space-y-4">
        <!-- Active Progress Card -->
        <div class="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2.5">
              <div
                class="w-7 h-7 rounded-lg flex items-center justify-center transition-colors"
                :class="isRunning ? 'bg-indigo-600/20 text-indigo-400' : 'bg-slate-800 text-slate-400'"
              >
                <Activity class="w-4 h-4" :class="{ 'animate-pulse text-indigo-300': isRunning }" />
              </div>
              <div>
                <h4 class="text-sm font-semibold text-white">当前测定进度</h4>
                <p class="text-xs text-slate-400 font-mono">{{ phaseText }}</p>
              </div>
            </div>

            <div class="text-right">
              <div class="text-lg font-bold font-mono text-indigo-300">
                {{ currentPoint }} / {{ totalPoints }}
                <span class="text-xs font-normal text-slate-400">({{ progressPercent }}%)</span>
              </div>
            </div>
          </div>

          <!-- Progress Bar -->
          <div class="w-full bg-slate-800/80 rounded-full h-2 overflow-hidden">
            <div
              class="bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 h-full rounded-full transition-all duration-300"
              :style="{ width: `${progressPercent}%` }"
            ></div>
          </div>

          <div class="flex items-center justify-between text-xs font-mono text-slate-300 pt-0.5">
            <span>当前输入推杆: {{ (currentInputValue * 100).toFixed(1) }}%</span>
            <span class="flex items-center space-x-1.5" :class="isRunning ? 'text-indigo-400' : 'text-slate-500'">
              <Clock v-if="isRunning" class="w-3.5 h-3.5 animate-spin" />
              <span>{{ isRunning ? '测定运行中...' : '已就绪' }}</span>
            </span>
          </div>
        </div>

        <!-- Terminal-Style Log Console -->
        <div class="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-2.5 relative">
          <!-- Terminal Toolbar -->
          <div class="flex items-center justify-between border-b border-slate-800 pb-2">
            <div class="flex items-center space-x-2">
              <Terminal class="w-4 h-4 text-emerald-400" />
              <span class="text-xs font-semibold text-white">测定执行诊断日志</span>
              <span class="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-400 font-mono">
                {{ sessionStore.measurementLogs.length }}
              </span>
            </div>

            <div class="flex items-center space-x-1.5">
              <button
                @click="autoScroll = !autoScroll"
                class="px-2 py-1 rounded text-[11px] font-mono transition cursor-pointer border flex items-center space-x-1"
                :class="autoScroll ? 'bg-indigo-950/60 border-indigo-700 text-indigo-300' : 'bg-slate-800 border-slate-700 text-slate-400'"
                title="切换自动滚屏"
              >
                <span>自动滚动</span>
                <span class="w-1.5 h-1.5 rounded-full" :class="autoScroll ? 'bg-emerald-400' : 'bg-slate-600'"></span>
              </button>

              <button
                @click="copyLogs"
                class="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer"
                title="复制全部日志"
              >
                <Check v-if="copied" class="w-3.5 h-3.5 text-emerald-400" />
                <Copy v-else class="w-3.5 h-3.5" />
              </button>

              <button
                @click="sessionStore.clearLogs"
                class="p-1 rounded text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition cursor-pointer"
                title="清空日志"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- Log Entries Container -->
          <div
            ref="logContainerRef"
            @scroll="onLogScroll"
            class="h-[260px] overflow-y-auto font-mono text-xs p-2.5 space-y-1.5 bg-slate-950 rounded-xl border border-slate-800/80 select-text"
          >
            <div
              v-if="sessionStore.measurementLogs.length === 0"
              class="h-full flex items-center justify-center text-slate-600 text-xs text-center select-none"
            >
              点击「开始稳态测定」，实时诊断日志与手柄动作将在此输出...
            </div>

            <div
              v-for="log in sessionStore.measurementLogs"
              :key="log.id"
              class="flex items-start space-x-2 text-[11px] leading-relaxed hover:bg-slate-900/60 px-1 py-0.5 rounded transition-colors"
            >
              <span class="text-slate-500 shrink-0 select-none">[{{ log.timestamp }}]</span>
              <span
                class="px-1.5 py-0.2 rounded text-[9px] shrink-0 uppercase font-semibold border"
                :class="getLogLevelClass(log.level)"
              >
                {{ log.level }}
              </span>
              <span class="text-slate-200 break-all">{{ log.message }}</span>
            </div>
          </div>

          <!-- Floating Return to Bottom Button -->
          <button
            v-if="!autoScroll && sessionStore.measurementLogs.length > 0"
            @click="scrollToBottom"
            class="absolute bottom-6 right-6 bg-indigo-600/90 hover:bg-indigo-500 text-white text-[11px] px-2.5 py-1 rounded-full shadow-lg border border-indigo-400/40 flex items-center space-x-1 cursor-pointer transition"
          >
            <ArrowDown class="w-3 h-3" />
            <span>滚动至最新</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Measured Points Real-time Table / Summary -->
    <div v-if="displayPoints && displayPoints.length > 0" class="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <CheckCircle2 class="w-4 h-4 text-emerald-400" />
          <span class="text-sm font-semibold text-white">
            采样点测定记录
            <span class="text-xs text-slate-400 font-normal">
              (已记录 {{ displayPoints.length }} / {{ totalPoints }} 点{{ isRunning ? ' · 实时采集中' : '' }})
            </span>
          </span>
        </div>
        <span class="text-xs text-slate-400">
          {{ isRunning ? '正在实时追加数据...' : `测定完成: ${lastResult?.measured_at || '刚刚'}` }}
        </span>
      </div>

      <div class="max-h-64 overflow-y-auto rounded-lg border border-slate-800">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-800/80 text-slate-300 sticky top-0">
            <tr>
              <th class="p-2.5">#</th>
              <th class="p-2.5">输入推杆量</th>
              <th class="p-2.5">角速度 (px/s)</th>
              <th class="p-2.5">归一化比例</th>
              <th class="p-2.5">稳定性评分</th>
              <th class="p-2.5">状态</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 font-mono">
            <tr
              v-for="(pt, idx) in displayPoints"
              :key="idx"
              class="transition-colors"
              :class="[
                idx === displayPoints.length - 1 && isRunning ? 'bg-indigo-950/30' : 'hover:bg-slate-800/30',
                !pt.valid ? 'text-rose-400/80' : 'text-slate-200'
              ]"
            >
              <td class="p-2.5 text-slate-500">{{ idx + 1 }}</td>
              <td class="p-2.5 font-bold">{{ (pt.input * 100).toFixed(1) }}%</td>
              <td class="p-2.5 font-semibold">
                {{ pt.velocity_px_s !== null ? `${pt.velocity_px_s} px/s` : '无效' }}
              </td>
              <td class="p-2.5 text-emerald-400">
                {{ pt.normalized_speed !== null ? `${(pt.normalized_speed * 100).toFixed(1)}%` : (isRunning ? '计算中...' : '-') }}
              </td>
              <td class="p-2.5">{{ Math.round(pt.stability * 100) }}%</td>
              <td class="p-2.5">
                <span
                  class="px-1.5 py-0.5 rounded text-[10px]"
                  :class="pt.valid ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-rose-950 text-rose-300 border border-rose-800'"
                >
                  {{ pt.valid ? '有效' : '重试失稳' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Navigation Buttons -->
    <div class="flex items-center space-x-4 pt-4 border-t border-slate-800">
      <button
        @click="goBack"
        :disabled="isRunning"
        class="flex-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700 text-slate-200 font-semibold py-2.5 px-4 rounded-xl flex items-center justify-center space-x-2 transition cursor-pointer"
      >
        <ArrowLeft class="w-4 h-4" />
        <span>上一步：死区调整</span>
      </button>
      <button
        @click="proceedToAnalysis"
        :disabled="!hasCompleted"
        class="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold py-2.5 px-4 rounded-xl shadow-lg shadow-indigo-600/30 flex items-center justify-center space-x-2 transition cursor-pointer"
      >
        <span>下一步：拟合分析与导出报告</span>
        <ArrowRight class="w-4 h-4" />
      </button>
    </div>
  </div>
</template>
