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
const importedResult = computed(() => sessionStore.importedResult)
const points = computed(() => result.value?.points || [])
const analysis = computed(() => result.value?.analysis)
const noise = computed(() => result.value?.noise)

const curveTypeLabels: Record<string, { label: string; desc: string }> = {
  linear: {
    label: '线性曲线 (Linear)',
    desc: '摇杆响应速度随推杆行程严格呈正比线性增加，手感均匀可预测。',
  },
  exponential: {
    label: '指数加速曲线 (Exponential)',
    desc: '微推段响应平缓柔和易微调，大推段加速明显，适合兼顾瞄准与大范围转向。',
  },
  s_curve: {
    label: 'S型平滑曲线 (S-Curve / Monotonic Logistic)',
    desc: '死区过渡与外圈饱和段均平滑过渡，中部线性区间大。',
  },
  undetermined: {
    label: '复杂/自定义曲线 (Undetermined)',
    desc: '未能完美匹配单一经典响应模型，可能包含复杂的多段折线或游戏厂商特调加速。',
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
      <div class="lg:col-span-8 p-5 bg-white border border-neutral-200/80 rounded-xl space-y-3 shadow-xs">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <Sparkles class="w-4 h-4 text-neutral-900" />
            <h3 class="text-sm font-semibold text-neutral-900">{{ currentTypeInfo.label }}</h3>
          </div>
          <div v-if="analysis?.confidence" class="px-2.5 py-0.5 bg-neutral-100 rounded-full text-xs font-mono text-neutral-700">
            拟合置信度: <span class="font-bold text-neutral-900">{{ (analysis.confidence * 100).toFixed(1) }}%</span>
          </div>
        </div>
        <p class="text-xs text-neutral-500 leading-relaxed">{{ currentTypeInfo.desc }}</p>

        <div v-if="analysis?.metrics && Object.keys(analysis.metrics).length > 0" class="flex flex-wrap gap-2 pt-1 font-mono text-[11px]">
          <span
            v-for="(val, key) in analysis.metrics"
            :key="key"
            class="px-2 py-0.5 bg-neutral-50 rounded border border-neutral-200/80 text-neutral-700"
          >
            {{ key }}: {{ val }}
          </span>
        </div>
      </div>

      <!-- Action & Export Tools -->
      <div class="lg:col-span-4 p-5 bg-white border border-neutral-200/80 rounded-xl flex flex-col justify-between space-y-3 shadow-xs">
        <div class="space-y-1">
          <div class="text-xs font-semibold uppercase tracking-wider text-neutral-700">报告导出与共享</div>
          <p class="text-[11px] text-neutral-400">将响应曲线导出为标准化文件，方便存档与跨软件复盘</p>
        </div>

        <div class="grid grid-cols-2 gap-2">
          <button
            @click="downloadExport('json')"
            :disabled="points.length === 0"
            class="py-2 px-3 bg-neutral-900 hover:bg-neutral-800 disabled:opacity-30 text-white text-xs rounded-lg flex items-center justify-center space-x-1.5 transition cursor-pointer font-medium"
          >
            <Download class="w-3.5 h-3.5" />
            <span>导出 JSON</span>
          </button>
          <button
            @click="downloadExport('csv')"
            :disabled="points.length === 0"
            class="py-2 px-3 bg-neutral-100 hover:bg-neutral-200 border border-neutral-200 disabled:opacity-30 text-neutral-800 text-xs rounded-lg flex items-center justify-center space-x-1.5 transition cursor-pointer font-medium"
          >
            <FileSpreadsheet class="w-3.5 h-3.5 text-neutral-700" />
            <span>导出 CSV</span>
          </button>
        </div>

        <div class="pt-2 border-t border-neutral-100 flex items-center justify-between">
          <button
            @click="triggerImport"
            class="text-xs text-neutral-600 hover:text-neutral-900 flex items-center space-x-1 cursor-pointer transition"
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
            class="text-xs text-neutral-400 hover:text-neutral-700 flex items-center space-x-1 cursor-pointer transition"
          >
            <RotateCcw class="w-3.5 h-3.5" />
            <span>重新测定</span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="importMessage" class="p-3 bg-neutral-100 border border-neutral-200 rounded-lg text-xs text-neutral-800">
      {{ importMessage }}
    </div>

    <!-- Main Chart Section -->
    <div class="p-5 bg-white border border-neutral-200/80 rounded-xl space-y-4 shadow-xs">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <BarChart3 class="w-3.5 h-3.5 text-neutral-700" />
          <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-700">手柄响应曲线图表</h3>
        </div>
        <div class="flex items-center space-x-4 text-xs font-mono text-neutral-500">
          <span class="flex items-center space-x-1.5">
            <span class="w-3 h-0.5 bg-neutral-400 inline-block"></span>
            <span>内死区: {{ ((sessionStore.config?.inner_deadzone || 0) * 100).toFixed(1) }}%</span>
          </span>
          <span class="flex items-center space-x-1.5">
            <span class="w-3 h-0.5 bg-neutral-700 inline-block"></span>
            <span>外死区: {{ ((sessionStore.config?.outer_deadzone || 1) * 100).toFixed(1) }}%</span>
          </span>
        </div>
      </div>

      <div v-if="points.length > 0">
        <CurveChart
          :points="points"
          :imported-points="importedResult?.points ?? []"
          :inner-deadzone="sessionStore.config?.inner_deadzone"
          :outer-deadzone="sessionStore.config?.outer_deadzone"
        />
      </div>
      <div v-else class="h-64 flex flex-col items-center justify-center text-neutral-400 text-xs space-y-2">
        <Activity class="w-7 h-7 text-neutral-300" />
        <span>暂无测定数据，请在步骤 3 中启动测定</span>
      </div>
    </div>

    <!-- Data Table Breakdown -->
    <div v-if="points.length > 0" class="p-5 bg-white border border-neutral-200/80 rounded-xl space-y-3 shadow-xs">
      <div class="flex items-center justify-between">
        <span class="text-xs font-semibold uppercase tracking-wider text-neutral-700">各采样点详表</span>
        <span v-if="noise" class="text-xs font-mono text-neutral-500">
          校准静止噪底: X={{ noise.floor_x }} px/s, Y={{ noise.floor_y }} px/s
        </span>
      </div>

      <div class="max-h-60 overflow-y-auto rounded-lg border border-neutral-200">
        <table class="w-full text-left text-xs font-mono">
          <thead class="bg-neutral-100 text-neutral-600 sticky top-0">
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
          <tbody class="divide-y divide-neutral-100 text-neutral-800">
            <tr v-for="(pt, idx) in points" :key="idx" class="hover:bg-neutral-50">
              <td class="p-2 text-neutral-400">{{ idx + 1 }}</td>
              <td class="p-2 font-bold">{{ (pt.input * 100).toFixed(1) }}%</td>
              <td class="p-2 font-medium">{{ pt.velocity_px_s !== null ? `${pt.velocity_px_s} px/s` : '-' }}</td>
              <td class="p-2">{{ pt.normalized_speed !== null ? `${(pt.normalized_speed * 100).toFixed(1)}%` : '-' }}</td>
              <td class="p-2">{{ Math.round(pt.stability * 100) }}%</td>
              <td class="p-2 text-neutral-500">{{ pt.attempts }} 次</td>
              <td class="p-2">
                <span :class="pt.valid ? 'text-neutral-900 font-medium' : 'text-rose-600'">
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
