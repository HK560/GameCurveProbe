<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSessionStore } from '../stores/session'
import { api } from '../services/api'
import CurveChart from './CurveChart.vue'
import { 
  BarChart3, 
  Download, 
  Upload, 
  Sparkles, 
  RotateCcw, 
  Activity,
  FileSpreadsheet
} from 'lucide-vue-next'

const sessionStore = useSessionStore()
const fileInput = ref<HTMLInputElement | null>(null)
const importMessage = ref<string | null>(null)

const result = computed(() => sessionStore.lastResult)
const points = computed(() => result.value?.points || [])
const analysis = computed(() => result.value?.analysis)
const noise = computed(() => result.value?.noise)

const curveTypeLabels: Record<string, { label: string; desc: string; color: string }> = {
  linear: {
    label: '线性曲线 (Linear)',
    desc: '摇杆响应速度随推杆行程严格呈正比线性增加，手感均匀可预测。',
    color: 'text-indigo-400 border-indigo-500/50 bg-indigo-950/40',
  },
  exponential: {
    label: '指数加速曲线 (Exponential)',
    desc: '微推段响应平缓柔和易微调，大推段加速明显，适合兼顾瞄准与大范围转向。',
    color: 'text-purple-400 border-purple-500/50 bg-purple-950/40',
  },
  s_curve: {
    label: 'S型平滑曲线 (S-Curve / Monotonic Logistic)',
    desc: '死区过渡与外圈饱和段均平滑过渡，中部线性区间大。',
    color: 'text-emerald-400 border-emerald-500/50 bg-emerald-950/40',
  },
  undetermined: {
    label: '复杂/自定义曲线 (Undetermined)',
    desc: '未能完美匹配单一经典响应模型，可能包含复杂的多段折线或游戏厂商特调加速。',
    color: 'text-amber-400 border-amber-500/50 bg-amber-950/40',
  },
}

const currentTypeInfo = computed(() => {
  const t = analysis.value?.curve_type || 'undetermined'
  return curveTypeLabels[t] || curveTypeLabels.undetermined
})

async function downloadExport(format: 'json' | 'csv') {
  try {
    const blob = await api.exportResult(format)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `gamecurveprobe_result_${new Date().toISOString().slice(0, 10)}.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (err: any) {
    console.error('Export failed:', err)
  }
}

function triggerImport() {
  fileInput.value?.click()
}

async function handleFileSelected(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  try {
    const text = await file.text()
    await api.importResult(text)
    importMessage.value = `成功导入报告：${file.name}`
  } catch (err: any) {
    importMessage.value = `导入失败：${err.message || 'JSON 格式不兼容'}`
  }
}

function restartProbe() {
  sessionStore.activeStep = 3
}
</script>

<template>
  <div class="space-y-6">
    <!-- Top Summary Banner -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4">
      <!-- Curve Model Card -->
      <div class="lg:col-span-8 p-5 bg-slate-900/80 border rounded-2xl space-y-3" :class="currentTypeInfo.color">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2.5">
            <Sparkles class="w-5 h-5" />
            <h3 class="text-base font-bold">{{ currentTypeInfo.label }}</h3>
          </div>
          <div v-if="analysis?.confidence" class="px-2.5 py-1 bg-slate-800/80 rounded-full border border-slate-700 text-xs font-mono">
            拟合置信度: <span class="font-bold text-white">{{ (analysis.confidence * 100).toFixed(1) }}%</span>
          </div>
        </div>
        <p class="text-xs text-slate-300 leading-relaxed">{{ currentTypeInfo.desc }}</p>

        <div v-if="analysis?.metrics && Object.keys(analysis.metrics).length > 0" class="flex flex-wrap gap-2 pt-1 font-mono text-[11px]">
          <span
            v-for="(val, key) in analysis.metrics"
            :key="key"
            class="px-2 py-0.5 bg-slate-800/60 rounded border border-slate-700/60 text-slate-300"
          >
            {{ key }}: {{ val }}
          </span>
        </div>
      </div>

      <!-- Action & Export Tools -->
      <div class="lg:col-span-4 p-5 bg-slate-900/80 border border-slate-800 rounded-2xl flex flex-col justify-between space-y-3">
        <div class="space-y-1">
          <div class="text-xs font-semibold text-slate-300">报告导出与共享</div>
          <p class="text-[11px] text-slate-500">将响应曲线导出为标准化文件，方便在 Excel 分析或存档</p>
        </div>

        <div class="grid grid-cols-2 gap-2">
          <button
            @click="downloadExport('json')"
            :disabled="points.length === 0"
            class="py-2 px-3 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 border border-slate-700 text-slate-200 text-xs rounded-lg flex items-center justify-center space-x-1.5 transition cursor-pointer"
          >
            <Download class="w-3.5 h-3.5 text-indigo-400" />
            <span>导出 JSON</span>
          </button>
          <button
            @click="downloadExport('csv')"
            :disabled="points.length === 0"
            class="py-2 px-3 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 border border-slate-700 text-slate-200 text-xs rounded-lg flex items-center justify-center space-x-1.5 transition cursor-pointer"
          >
            <FileSpreadsheet class="w-3.5 h-3.5 text-emerald-400" />
            <span>导出 CSV</span>
          </button>
        </div>

        <div class="pt-2 border-t border-slate-800/80 flex items-center justify-between">
          <button
            @click="triggerImport"
            class="text-xs text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 cursor-pointer"
          >
            <Upload class="w-3.5 h-3.5" />
            <span>导入历史报告...</span>
          </button>
          <input
            ref="fileInput"
            type="file"
            accept=".json"
            class="hidden"
            @change="handleFileSelected"
          />

          <button
            @click="restartProbe"
            class="text-xs text-slate-400 hover:text-slate-200 flex items-center space-x-1 cursor-pointer"
          >
            <RotateCcw class="w-3.5 h-3.5" />
            <span>重新测定</span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="importMessage" class="p-3 bg-indigo-950/50 border border-indigo-500/40 rounded-xl text-xs text-indigo-300">
      {{ importMessage }}
    </div>

    <!-- Main Chart Section -->
    <div class="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <BarChart3 class="w-4 h-4 text-indigo-400" />
          <h3 class="text-sm font-semibold text-white">手柄响应曲线图表</h3>
        </div>
        <div class="flex items-center space-x-3 text-xs">
          <span class="flex items-center space-x-1 text-amber-400">
            <span class="w-2.5 h-0.5 bg-amber-400 inline-block"></span>
            <span>内死区: {{ ((sessionStore.config?.inner_deadzone || 0) * 100).toFixed(1) }}%</span>
          </span>
          <span class="flex items-center space-x-1 text-purple-400">
            <span class="w-2.5 h-0.5 bg-purple-400 inline-block"></span>
            <span>外死区: {{ ((sessionStore.config?.outer_deadzone || 1) * 100).toFixed(1) }}%</span>
          </span>
        </div>
      </div>

      <div v-if="points.length > 0">
        <CurveChart
          :points="points"
          :inner-deadzone="sessionStore.config?.inner_deadzone"
          :outer-deadzone="sessionStore.config?.outer_deadzone"
        />
      </div>
      <div v-else class="h-64 flex flex-col items-center justify-center text-slate-500 text-xs space-y-2">
        <Activity class="w-8 h-8 text-slate-600" />
        <span>暂无测定数据，请在步骤 3 中启动测定</span>
      </div>
    </div>

    <!-- Data Table Breakdown -->
    <div v-if="points.length > 0" class="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-3">
      <div class="flex items-center justify-between">
        <span class="text-xs font-semibold text-slate-200">各采样点详表</span>
        <span v-if="noise" class="text-xs font-mono text-cyan-400">
          校准静止噪底: X={{ noise.floor_x }} px/s, Y={{ noise.floor_y }} px/s
        </span>
      </div>

      <div class="max-h-60 overflow-y-auto rounded-lg border border-slate-800">
        <table class="w-full text-left text-xs font-mono">
          <thead class="bg-slate-800 text-slate-400 sticky top-0">
            <tr>
              <th class="p-2">#</th>
              <th class="p-2">摇杆输入 (X)</th>
              <th class="p-2">角速度 (px/s)</th>
              <th class="p-2">归一化比例</th>
              <th class="p-2">稳定性</th>
              <th class="p-2">采样尝试</th>
              <th class="p-2">状态</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            <tr v-for="(pt, idx) in points" :key="idx" class="hover:bg-slate-800/30">
              <td class="p-2 text-slate-500">{{ idx + 1 }}</td>
              <td class="p-2 font-bold">{{ (pt.input * 100).toFixed(1) }}%</td>
              <td class="p-2 text-indigo-300">{{ pt.velocity_px_s !== null ? `${pt.velocity_px_s} px/s` : '-' }}</td>
              <td class="p-2 text-emerald-400">{{ pt.normalized_speed !== null ? `${(pt.normalized_speed * 100).toFixed(1)}%` : '-' }}</td>
              <td class="p-2">{{ Math.round(pt.stability * 100) }}%</td>
              <td class="p-2 text-slate-400">{{ pt.attempts }} 次</td>
              <td class="p-2">
                <span :class="pt.valid ? 'text-emerald-400' : 'text-rose-400'">
                  {{ pt.valid ? '有效' : '失稳' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
