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
    <div class="p-4 bg-white border border-neutral-200/80 rounded-xl space-y-4 shadow-xs">
      <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
        <div class="flex items-center space-x-2">
          <Sliders class="w-3.5 h-3.5 text-neutral-700" />
          <span class="text-xs font-semibold uppercase tracking-wider text-neutral-700">采样参数配置</span>
        </div>
        <div class="text-xs text-neutral-400">
          基于当前死区: 内死区 {{ ((sessionStore.config?.inner_deadzone || 0) * 100).toFixed(1) }}%, 
          外死区 {{ ((sessionStore.config?.outer_deadzone || 1) * 100).toFixed(1) }}%
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
        <div class="space-y-1.5">
          <label class="text-xs font-medium text-neutral-700">测定范围模式</label>
          <select
            v-model="rangeMode"
            :disabled="isRunning"
            class="w-full bg-neutral-50 hover:bg-white focus:bg-white border border-neutral-200 rounded-lg px-3 py-2 text-sm text-neutral-900 focus:outline-none focus:border-neutral-900 transition disabled:opacity-50"
          >
            <option value="full">全范围 (内死区至外死区)</option>
            <option value="active_range">有效行程（内死区至外死区）</option>
          </select>
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-medium text-neutral-700">采样点密度</label>
          <select
            v-model.number="pointCount"
            :disabled="isRunning"
            class="w-full bg-neutral-50 hover:bg-white focus:bg-white border border-neutral-200 rounded-lg px-3 py-2 text-sm text-neutral-900 focus:outline-none focus:border-neutral-900 transition disabled:opacity-50"
          >
            <option :value="9">9 点 (快速摸底, ~15秒)</option>
            <option :value="17">17 点 (标准推荐, ~30秒)</option>
            <option :value="33">33 点 (高精密度, ~60秒)</option>
          </select>
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-medium text-neutral-700">单点稳定/采样时长</label>
          <div class="px-3 py-2 bg-neutral-50 border border-neutral-200/80 rounded-lg text-xs font-mono text-neutral-700 flex items-center justify-between">
            <span>Settle: {{ sessionStore.config?.settle_ms }}ms</span>
            <span>Sample: {{ sessionStore.config?.sample_ms }}ms</span>
          </div>
        </div>

        <div>
          <button
            v-if="!isRunning"
            @click="startMeasurement"
            class="w-full bg-neutral-900 hover:bg-neutral-800 text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center space-x-2 transition cursor-pointer text-sm"
          >
            <Play class="w-3.5 h-3.5 fill-current" />
            <span>开始稳态测定</span>
          </button>
          <button
            v-else
            @click="cancelMeasurement"
            class="w-full bg-rose-600 hover:bg-rose-700 text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center space-x-2 transition cursor-pointer text-sm"
          >
            <Square class="w-3.5 h-3.5 fill-current" />
            <span>中止当前任务</span>
          </button>
        </div>
      </div>
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
          <div class="flex items-center justify-between border-b border-neutral-100 pb-2.5">
            <div class="flex items-center space-x-2">
              <Camera class="w-3.5 h-3.5 text-neutral-700" />
              <span class="text-xs font-semibold uppercase tracking-wider text-neutral-700">实时画面与追踪监控</span>
            </div>
            <div class="flex items-center space-x-2 text-xs">
              <span
                class="w-2 h-2 rounded-full"
                :class="sessionStore.livePreviewUrl ? 'bg-emerald-500' : 'bg-neutral-400'"
              ></span>
              <span class="text-neutral-500 font-mono text-[11px]">
                {{ sessionStore.capture ? `${sessionStore.capture.width}×${sessionStore.capture.height} @ ${sessionStore.capture.target_fps}Hz` : '画面未就绪' }}
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
                  <span>追踪ROI: {{ sessionStore.roi?.width }}×{{ sessionStore.roi?.height }}</span>
                </div>
              </div>
            </template>

            <div v-else class="text-center p-6 space-y-2 text-neutral-500">
              <Camera class="w-7 h-7 mx-auto stroke-1 opacity-50" />
              <p class="text-xs">暂未获取到实时画面</p>
              <p class="text-[11px] text-neutral-400">请先在「窗口与抓图」步骤绑定游戏窗口</p>
            </div>
          </div>

          <!-- Viewport Info Footer -->
          <div class="flex items-center justify-between text-xs text-neutral-500 pt-1 font-mono">
            <div class="flex items-center space-x-2">
              <span class="px-2 py-0.5 rounded bg-neutral-100 text-[11px] text-neutral-700">
                后端: {{ sessionStore.capture?.backend?.toUpperCase() || 'NONE' }}
              </span>
              <span class="text-neutral-300">|</span>
              <span class="text-[11px] text-neutral-500">
                安全遮挡防护: {{ sessionStore.capture?.occlusion_safe ? '开启' : '关闭' }}
              </span>
            </div>
            <div class="text-right text-neutral-900 font-medium text-[11px]">
              推杆状态: {{ (currentInputValue * 100).toFixed(1) }}% (X+)
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
                class="w-7 h-7 rounded-lg flex items-center justify-center transition-colors bg-neutral-100 text-neutral-900"
              >
                <Activity class="w-4 h-4" :class="{ 'animate-pulse text-neutral-900': isRunning }" />
              </div>
              <div>
                <h4 class="text-xs font-semibold uppercase tracking-wider text-neutral-700">当前测定进度</h4>
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
            <span>当前输入推杆: {{ (currentInputValue * 100).toFixed(1) }}%</span>
            <span class="flex items-center space-x-1.5" :class="isRunning ? 'text-neutral-900 font-medium' : 'text-neutral-400'">
              <Clock v-if="isRunning" class="w-3 h-3 animate-spin" />
              <span>{{ isRunning ? '测定运行中...' : '已就绪' }}</span>
            </span>
          </div>
        </div>

        <!-- Terminal-Style Log Console -->
        <div class="p-4 bg-white border border-neutral-200/80 rounded-xl space-y-2.5 relative shadow-xs">
          <!-- Terminal Toolbar -->
          <div class="flex items-center justify-between border-b border-neutral-100 pb-2">
            <div class="flex items-center space-x-2">
              <Terminal class="w-3.5 h-3.5 text-neutral-700" />
              <span class="text-xs font-semibold uppercase tracking-wider text-neutral-700">诊断日志</span>
              <span class="text-[10px] px-1.5 py-0.2 rounded-full bg-neutral-100 text-neutral-500 font-mono">
                {{ sessionStore.measurementLogs.length }}
              </span>
            </div>

            <div class="flex items-center space-x-1.5">
              <button
                @click="autoScroll = !autoScroll"
                class="px-2 py-0.5 rounded text-[11px] font-mono transition cursor-pointer border flex items-center space-x-1"
                :class="autoScroll ? 'bg-neutral-900 border-neutral-900 text-white' : 'bg-neutral-100 border-neutral-200 text-neutral-600'"
                title="切换自动滚屏"
              >
                <span>滚动</span>
                <span class="w-1.5 h-1.5 rounded-full" :class="autoScroll ? 'bg-emerald-400' : 'bg-neutral-400'"></span>
              </button>

              <button
                @click="copyLogs"
                class="p-1 rounded text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100 transition cursor-pointer"
                title="复制全部日志"
              >
                <Check v-if="copied" class="w-3.5 h-3.5 text-neutral-900" />
                <Copy v-else class="w-3.5 h-3.5" />
              </button>

              <button
                @click="sessionStore.clearLogs"
                class="p-1 rounded text-neutral-500 hover:text-rose-600 hover:bg-neutral-100 transition cursor-pointer"
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
            class="h-[240px] overflow-y-auto font-mono text-xs p-2.5 space-y-1.5 bg-neutral-950 text-neutral-200 rounded-lg border border-neutral-800 select-text"
          >
            <div
              v-if="sessionStore.measurementLogs.length === 0"
              class="h-full flex items-center justify-center text-neutral-500 text-xs text-center select-none"
            >
              点击「开始稳态测定」，实时诊断日志将在此输出...
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
            <span>最新</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Measured Points Real-time Table / Summary -->
    <div v-if="displayPoints && displayPoints.length > 0" class="p-5 bg-white border border-neutral-200/80 rounded-xl space-y-3 shadow-xs">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <CheckCircle2 class="w-4 h-4 text-neutral-900" />
          <span class="text-xs font-semibold uppercase tracking-wider text-neutral-700">
            采样点测定记录
            <span class="text-neutral-400 font-normal">
              ({{ displayPoints.length }} / {{ totalPoints }} 点{{ isRunning ? ' · 采集中' : '' }})
            </span>
          </span>
        </div>
        <span class="text-[11px] text-neutral-400 font-mono">
          {{ isRunning ? '正在实时追加数据...' : `测定完成: ${lastResult?.measured_at || '刚刚'}` }}
        </span>
      </div>

      <div class="max-h-64 overflow-y-auto rounded-lg border border-neutral-200">
        <table class="w-full text-left text-xs">
          <thead class="bg-neutral-100 text-neutral-600 sticky top-0">
            <tr>
              <th class="p-2.5">#</th>
              <th class="p-2.5">输入推杆量</th>
              <th class="p-2.5">角速度 (px/s)</th>
              <th class="p-2.5">归一化比例</th>
              <th class="p-2.5">稳定性评分</th>
              <th class="p-2.5">状态</th>
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
                {{ pt.velocity_px_s !== null ? `${pt.velocity_px_s} px/s` : '无效' }}
              </td>
              <td class="p-2.5">
                {{ pt.normalized_speed !== null ? `${(pt.normalized_speed * 100).toFixed(1)}%` : (isRunning ? '计算中...' : '-') }}
              </td>
              <td class="p-2.5">{{ Math.round(pt.stability * 100) }}%</td>
              <td class="p-2.5">
                <span
                  class="px-1.5 py-0.5 rounded text-[10px]"
                  :class="pt.valid ? 'bg-neutral-100 text-neutral-800 border border-neutral-200' : 'bg-rose-50 text-rose-600 border border-rose-200'"
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
    <div class="flex items-center space-x-4 pt-2">
      <button
        @click="goBack"
        :disabled="isRunning"
        class="flex-1 bg-neutral-100 hover:bg-neutral-200 disabled:opacity-40 text-neutral-700 font-medium py-2.5 px-4 rounded-lg flex items-center justify-center space-x-2 transition cursor-pointer text-xs"
      >
        <ArrowLeft class="w-4 h-4" />
        <span>上一步：死区调整</span>
      </button>
      <button
        @click="proceedToAnalysis"
        :disabled="!hasCompleted"
        class="flex-1 bg-neutral-900 hover:bg-neutral-800 disabled:opacity-30 disabled:cursor-not-allowed text-white font-medium py-2.5 px-4 rounded-lg flex items-center justify-center space-x-2 transition cursor-pointer text-xs"
      >
        <span>下一步：拟合分析与导出报告</span>
        <ArrowRight class="w-4 h-4" />
      </button>
    </div>
  </div>
</template>
