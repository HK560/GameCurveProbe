<script setup lang="ts">
import { ref, computed } from 'vue'
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
  Clock
} from 'lucide-vue-next'
import type { RangeMode } from '../types/api'

const sessionStore = useSessionStore()

const rangeMode = ref<RangeMode>(sessionStore.config?.range_mode || 'full')
const pointCount = ref<number>(sessionStore.config?.point_count || 17)
const errorMessage = ref<string | null>(null)

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
    <div class="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-4">
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
            <option value="outer_only">仅外死区段 (0.7 ~ 1.0)</option>
            <option value="deadzone_only">仅死区段 (0.0 ~ 0.2)</option>
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

    <!-- Active Task Progress Indicator -->
    <div v-if="isRunning" class="p-5 bg-indigo-950/40 border border-indigo-500/40 rounded-2xl space-y-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 rounded-lg bg-indigo-600/30 text-indigo-300 flex items-center justify-center">
            <Activity class="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h4 class="text-sm font-semibold text-white">正在全自动遍历采样点...</h4>
            <p class="text-xs text-indigo-300/80">手柄已自动输出，请勿触碰物理手柄摇杆</p>
          </div>
        </div>
        <div class="text-right">
          <div class="text-xs text-slate-400">进度</div>
          <div class="text-lg font-bold font-mono text-indigo-300">{{ currentPoint }} / {{ totalPoints }} ({{ progressPercent }}%)</div>
        </div>
      </div>

      <!-- Progress Bar -->
      <div class="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
        <div
          class="bg-gradient-to-r from-indigo-500 to-purple-500 h-full rounded-full transition-all duration-300"
          :style="{ width: `${progressPercent}%` }"
        ></div>
      </div>

      <div class="flex items-center justify-between text-xs text-slate-300 font-mono">
        <span>当前推杆量: {{ progressData?.input_value !== undefined ? (progressData.input_value * 100).toFixed(1) : 0 }}%</span>
        <span class="flex items-center space-x-1 text-indigo-400">
          <Clock class="w-3.5 h-3.5 animate-spin" />
          <span>稳态捕获中...</span>
        </span>
      </div>
    </div>

    <!-- Measured Points Real-time Table / Summary -->
    <div v-if="lastResult?.points && lastResult.points.length > 0" class="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <CheckCircle2 class="w-4 h-4 text-emerald-400" />
          <span class="text-sm font-semibold text-white">测定数据预览 (已记录 {{ lastResult.points.length }} 个采样点)</span>
        </div>
        <span class="text-xs text-slate-400">测定时间: {{ lastResult.measured_at || '刚刚' }}</span>
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
              v-for="(pt, idx) in lastResult.points"
              :key="idx"
              class="hover:bg-slate-800/30"
              :class="!pt.valid ? 'text-rose-400/80' : 'text-slate-200'"
            >
              <td class="p-2.5 text-slate-500">{{ idx + 1 }}</td>
              <td class="p-2.5 font-bold">{{ (pt.input * 100).toFixed(1) }}%</td>
              <td class="p-2.5">{{ pt.velocity_px_s !== null ? `${pt.velocity_px_s} px/s` : '无效' }}</td>
              <td class="p-2.5 text-emerald-400">{{ pt.normalized_speed !== null ? `${(pt.normalized_speed * 100).toFixed(1)}%` : '-' }}</td>
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
