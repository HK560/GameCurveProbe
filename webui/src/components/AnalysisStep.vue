<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useSessionStore } from '../stores/session'
import { api } from '../services/api'
import CurveChart from './CurveChart.vue'
import { fitResponseCurve, type FitModelType, type FitCandidate } from '../services/curveFitting'
import { t } from '../services/i18n'
import { useTutorial } from '../composables/useTutorial'
import { 
  BarChart3, 
  Download, 
  Upload, 
  Sparkles, 
  RotateCcw, 
  Activity,
  FileSpreadsheet,
  Sliders
} from 'lucide-vue-next'

const sessionStore = useSessionStore()
const tutorial = useTutorial()
const fileInput = ref<HTMLInputElement | null>(null)
const importMessage = ref<string | null>(null)

const result = computed(() => tutorial.active.value ? tutorial.demo.result : sessionStore.lastResult)
const importedResult = computed(() => tutorial.active.value ? null : sessionStore.importedResult)
const points = computed(() => result.value?.points || [])
const noise = computed(() => result.value?.noise)

// Analysis Deadzone Filter Range
const analysisInnerDeadzone = ref<number>(0.0)
const analysisOuterDeadzone = ref<number>(1.0)

watch(
  () => result.value,
  (res) => {
    if (res?.config) {
      analysisInnerDeadzone.value = res.config.inner_deadzone ?? 0.0
      analysisOuterDeadzone.value = res.config.outer_deadzone ?? 1.0
    } else {
      analysisInnerDeadzone.value = 0.0
      analysisOuterDeadzone.value = 1.0
    }
  },
  { immediate: true }
)

const resetDeadzoneRange = (inner: number, outer: number) => {
  analysisInnerDeadzone.value = inner
  analysisOuterDeadzone.value = outer
}

// Recalculate normalized values & active range tags for points
const recalculatedPoints = computed(() => {
  const raw = points.value
  if (!raw || raw.length === 0) return []

  const inner = analysisInnerDeadzone.value
  const outer = analysisOuterDeadzone.value

  const validInRange = raw.filter(
    (p) => p.valid && p.velocity_px_s !== null && p.input >= inner - 1e-5 && p.input <= outer + 1e-5
  )

  if (validInRange.length === 0) {
    return raw.map((p) => ({
      ...p,
      in_analysis_range: p.input >= inner - 1e-5 && p.input <= outer + 1e-5,
      normalized_speed: p.normalized_speed,
    }))
  }

  const vMin = Math.min(...validInRange.map((p) => p.velocity_px_s!))
  const vMax = Math.max(...validInRange.map((p) => p.velocity_px_s!))
  const vRange = vMax - vMin

  return raw.map((p) => {
    const inRange = p.input >= inner - 1e-5 && p.input <= outer + 1e-5
    let norm: number | null = null

    if (p.valid && p.velocity_px_s !== null) {
      if (p.input < inner - 1e-5) {
        norm = 0.0
      } else if (p.input > outer + 1e-5) {
        norm = 1.0
      } else {
        norm = vRange > 1e-6 ? (p.velocity_px_s - vMin) / vRange : 1.0
        norm = Math.max(0.0, Math.min(1.0, norm))
      }
    } else {
      norm = p.normalized_speed
    }

    return {
      ...p,
      in_analysis_range: inRange,
      normalized_speed: norm !== null ? Math.round(norm * 10000) / 10000 : null,
    }
  })
})

// Selected Model for Comparison ('auto' or specific candidate)
const selectedModelType = ref<'auto' | FitModelType>('auto')

// Compute curve fitting report
const fitReport = computed(() => {
  if (recalculatedPoints.value.length === 0) return null
  return fitResponseCurve(
    recalculatedPoints.value,
    analysisInnerDeadzone.value,
    analysisOuterDeadzone.value
  )
})

// Active candidate based on selection
const activeCandidate = computed<FitCandidate | null>(() => {
  if (!fitReport.value) return null
  if (selectedModelType.value === 'auto') {
    return fitReport.value.best
  }
  return fitReport.value.candidates[selectedModelType.value] || fitReport.value.best
})

// Recalculate analysis metrics for export compatibility
const recalculatedAnalysis = computed(() => {
  if (!activeCandidate.value) {
    return {
      curve_type: 'undetermined',
      confidence: 0.0,
      metrics: { note: t('note_nodes_insufficient') },
    }
  }

  return {
    curve_type: activeCandidate.value.type,
    confidence: Math.round(activeCandidate.value.confidence * 10000) / 10000,
    metrics: {
      ...activeCandidate.value.params,
      r2: Math.round(activeCandidate.value.r2 * 10000) / 10000,
      nrmse: Math.round(activeCandidate.value.nrmse * 10000) / 10000,
      bic: Math.round(activeCandidate.value.bic * 10) / 10,
    },
  }
})

const modelOptions = computed(() => [
  {
    type: 'auto' as const,
    label: `${t('model_auto_label')}${fitReport.value ? ` (${fitReport.value.best.type})` : ''}`,
  },
  { type: 'linear' as const, label: t('model_linear_label') },
  { type: 'power' as const, label: t('model_power_label') },
  { type: 'piecewise1' as const, label: t('model_piecewise1_label') },
  { type: 'piecewise2' as const, label: t('model_piecewise2_label') },
  { type: 'bezier' as const, label: t('model_bezier_label') },
])

const curveTypeLabels = computed<Record<string, { label: string; desc: string }>>(() => ({
  linear: {
    label: t('model_linear_label'),
    desc: t('model_linear_desc'),
  },
  power: {
    label: t('model_power_label'),
    desc: t('model_power_desc'),
  },
  piecewise1: {
    label: t('model_piecewise1_label'),
    desc: t('model_piecewise1_desc'),
  },
  piecewise2: {
    label: t('model_piecewise2_label'),
    desc: t('model_piecewise2_desc'),
  },
  bezier: {
    label: t('model_bezier_label'),
    desc: t('model_bezier_desc'),
  },
  undetermined: {
    label: t('model_undetermined_label'),
    desc: t('model_undetermined_desc'),
  },
}))

const currentTypeInfo = computed(() => {
  if (!activeCandidate.value) {
    return {
      label: t('model_undetermined_label'),
      desc: t('model_undetermined_desc'),
    }
  }
  const curType = activeCandidate.value.type
  return curveTypeLabels.value[curType] || {
    label: activeCandidate.value.name,
    desc: t('model_linear_desc'),
  }
})

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

async function downloadExport(format: 'json' | 'csv') {
  if (recalculatedPoints.value.length === 0) return

  const dateStr = new Date().toISOString().slice(0, 10)
  const rangeStr = `${(analysisInnerDeadzone.value * 100).toFixed(0)}-${(analysisOuterDeadzone.value * 100).toFixed(0)}`
  const filename = `gamecurveprobe_analysis_${rangeStr}_${dateStr}.${format}`

  if (format === 'csv') {
    const headers = ['#', 'Input_Stick_X', 'Velocity_px_s', 'Recalculated_Normalized', 'Stability', 'Coverage', 'Attempts', 'In_Active_Range', 'Status']
    const rows = recalculatedPoints.value.map((p, idx) => [
      idx + 1,
      p.input.toFixed(4),
      p.velocity_px_s !== null ? p.velocity_px_s.toFixed(2) : '',
      p.normalized_speed !== null ? p.normalized_speed.toFixed(4) : '',
      p.stability.toFixed(4),
      ((p as any).coverage ?? p.stability).toFixed(4),
      p.attempts,
      p.in_analysis_range ? 'YES' : 'NO',
      p.valid ? (p.in_analysis_range ? 'Valid' : 'Outside_Deadzone') : 'Invalid',
    ])
    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    saveBlob(blob, filename)
  } else {
    const exportData = {
      id: (result.value as any)?.id || result.value?.session_id || 'export',
      measured_at: result.value?.measured_at || new Date().toISOString(),
      analysis_range: {
        inner_deadzone: analysisInnerDeadzone.value,
        outer_deadzone: analysisOuterDeadzone.value,
      },
      analysis: recalculatedAnalysis.value,
      points: recalculatedPoints.value,
      noise: noise.value,
    }
    const jsonContent = JSON.stringify(exportData, null, 2)
    const blob = new Blob([jsonContent], { type: 'application/json' })
    saveBlob(blob, filename)
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
    const parsed = JSON.parse(text)
    if (parsed && Array.isArray(parsed.points)) {
      sessionStore.loadSimulatedResult(parsed)
    }
    try {
      await api.importResult(text)
    } catch {
      // Backend not running in standalone demo mode, local load is sufficient
    }
    importMessage.value = `${t('import_success')} ${file.name}`
  } catch (err: any) {
    importMessage.value = `${t('import_failed')} ${err.message || t('json_parse_error')}`
  }
}

function restartProbe() {
  sessionStore.activeStep = 3
}
</script>

<template>
  <div class="space-y-6">
    <!-- Top Summary Banner -->
    <div data-tour="analysis-summary" class="grid grid-cols-1 lg:grid-cols-12 gap-4">
      <!-- Curve Model Card -->
      <div data-tour="analysis-model" class="lg:col-span-8 p-5 bg-white border border-neutral-200/80 rounded-xl space-y-3.5 shadow-xs">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center space-x-2">
            <div class="w-6 h-6 rounded-md bg-neutral-900 text-white flex items-center justify-center">
              <Sparkles class="w-3.5 h-3.5 text-neutral-100" />
            </div>
            <h3 class="text-sm font-semibold text-neutral-900">{{ currentTypeInfo.label }}</h3>
            <span
              v-if="selectedModelType === 'auto'"
              class="px-2 py-0.5 rounded text-[10px] font-medium bg-neutral-100 text-neutral-700 border border-neutral-200/80"
            >
              {{ t('model_auto_label') }}
            </span>
          </div>

          <div class="flex items-center space-x-2 font-mono text-xs">
            <div v-if="activeCandidate" class="px-2.5 py-0.5 bg-neutral-100 rounded-full text-neutral-700">
              {{ t('metric_confidence') }}: <span class="font-bold text-neutral-900">{{ (activeCandidate.confidence * 100).toFixed(1) }}%</span>
            </div>
            <div v-if="activeCandidate" class="px-2.5 py-0.5 bg-neutral-100 rounded-full text-neutral-700">
              {{ t('metric_r2') }}: <span class="font-bold text-neutral-900">{{ (activeCandidate.r2 * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>

        <p class="text-xs text-neutral-500 leading-relaxed">{{ currentTypeInfo.desc }}</p>

        <!-- Key Parameter Highlights -->
        <div v-if="activeCandidate" class="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-0.5 font-mono text-xs">
          <!-- Piecewise1 extra accel parameters -->
          <template v-if="activeCandidate.type === 'piecewise1'">
            <div class="p-2.5 bg-neutral-50 border border-neutral-200/70 rounded-lg">
              <span class="text-[10px] text-neutral-400 block">{{ t('metric_accel_threshold') }}</span>
              <span class="font-bold text-neutral-900 text-sm">{{ activeCandidate.params.accelThreshold }}</span>
            </div>
            <div class="p-2.5 bg-neutral-50 border border-neutral-200/70 rounded-lg">
              <span class="text-[10px] text-neutral-400 block">{{ t('metric_accel_ratio') }}</span>
              <span class="font-bold text-neutral-900 text-sm">{{ activeCandidate.params.boostRatio }}x</span>
            </div>
            <div class="p-2.5 bg-neutral-50 border border-neutral-200/70 rounded-lg">
              <span class="text-[10px] text-neutral-400 block">{{ t('metric_base_slope') }}</span>
              <span class="font-medium text-neutral-800">{{ activeCandidate.params.baseSlope }} px/s</span>
            </div>
          </template>

          <!-- Power curve parameters -->
          <template v-else-if="activeCandidate.type === 'power'">
            <div class="p-2.5 bg-neutral-50 border border-neutral-200/70 rounded-lg">
              <span class="text-[10px] text-neutral-400 block">{{ t('metric_gamma') }}</span>
              <span class="font-bold text-neutral-900 text-sm">{{ activeCandidate.params.gamma }}</span>
            </div>
            <div class="p-2.5 bg-neutral-50 border border-neutral-200/70 rounded-lg col-span-2">
              <span class="text-[10px] text-neutral-400 block">{{ t('status') }}</span>
              <span class="font-medium text-neutral-800">{{ activeCandidate.params.shape }}</span>
            </div>
          </template>

          <!-- Linear parameters -->
          <template v-else-if="activeCandidate.type === 'linear'">
            <div class="p-2.5 bg-neutral-50 border border-neutral-200/70 rounded-lg col-span-2 sm:col-span-3">
              <span class="text-[10px] text-neutral-400 block">{{ t('metric_base_slope') }}</span>
              <span class="font-bold text-neutral-900 text-sm">{{ activeCandidate.params.physicalSlope }} px/s</span>
            </div>
          </template>

          <!-- Piecewise2 parameters -->
          <template v-else-if="activeCandidate.type === 'piecewise2'">
            <div class="p-2.5 bg-neutral-50 border border-neutral-200/70 rounded-lg">
              <span class="text-[10px] text-neutral-400 block">拐点 1 / 2</span>
              <span class="font-bold text-neutral-900">{{ activeCandidate.params.breakpoint1 }} / {{ activeCandidate.params.breakpoint2 }}</span>
            </div>
            <div class="p-2.5 bg-neutral-50 border border-neutral-200/70 rounded-lg col-span-2">
              <span class="text-[10px] text-neutral-400 block">各段相对斜率 (k1 / k2 / k3)</span>
              <span class="font-medium text-neutral-800">{{ activeCandidate.params.k1 }} ➔ {{ activeCandidate.params.k2 }} ➔ {{ activeCandidate.params.k3 }}</span>
            </div>
          </template>

          <!-- Bezier parameters -->
          <template v-else-if="activeCandidate.type === 'bezier'">
            <div class="p-2.5 bg-neutral-50 border border-neutral-200/70 rounded-lg col-span-2 sm:col-span-3">
              <span class="text-[10px] text-neutral-400 block">控制点坐标 P1 / P2</span>
              <span class="font-medium text-neutral-800">{{ activeCandidate.params.p1 }} | {{ activeCandidate.params.p2 }}</span>
            </div>
          </template>
        </div>

        <!-- Model Comparison Switcher Pills -->
        <div class="pt-2.5 border-t border-neutral-100 flex flex-wrap items-center gap-1.5">
          <span class="text-[11px] text-neutral-500 font-medium mr-1">{{ t('model_selector_title') }}:</span>
          <button
            v-for="opt in modelOptions"
            :key="opt.type"
            type="button"
            @click="selectedModelType = opt.type"
            class="px-2.5 py-1 rounded text-[11px] font-medium transition cursor-pointer"
            :class="selectedModelType === opt.type
              ? 'bg-neutral-900 text-white shadow-xs'
              : 'bg-neutral-100 hover:bg-neutral-200 text-neutral-700'"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>

      <!-- Action & Export Tools -->
      <div data-tour="analysis-export" class="lg:col-span-4 p-5 bg-white border border-neutral-200/80 rounded-xl flex flex-col justify-between space-y-3 shadow-xs">
        <div class="flex items-center space-x-2.5 pb-2 border-b border-neutral-100">
          <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
            <Download class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">{{ t('export_and_share') }}</h3>
            <p class="text-[11px] text-neutral-400">{{ t('export_desc') }}</p>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-2">
          <button
            @click="downloadExport('json')"
            :disabled="recalculatedPoints.length === 0"
            class="py-2 px-3 bg-neutral-900 hover:bg-neutral-800 disabled:opacity-30 text-white text-xs rounded-lg flex items-center justify-center space-x-1.5 transition cursor-pointer font-medium"
          >
            <Download class="w-3.5 h-3.5" />
            <span>{{ t('export_json') }}</span>
          </button>
          <button
            @click="downloadExport('csv')"
            :disabled="recalculatedPoints.length === 0"
            class="py-2 px-3 bg-neutral-100 hover:bg-neutral-200 border border-neutral-200 disabled:opacity-30 text-neutral-800 text-xs rounded-lg flex items-center justify-center space-x-1.5 transition cursor-pointer font-medium"
          >
            <FileSpreadsheet class="w-3.5 h-3.5 text-neutral-700" />
            <span>{{ t('export_csv') }}</span>
          </button>
        </div>

        <div class="pt-2 border-t border-neutral-100 flex items-center justify-between">
          <button
            @click="triggerImport"
            class="text-xs text-neutral-600 hover:text-neutral-900 flex items-center space-x-1 cursor-pointer transition"
          >
            <Upload class="w-3.5 h-3.5" />
            <span>{{ t('import_history') }}</span>
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
            <span>{{ t('restart_probe') }}</span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="importMessage" class="p-3 bg-neutral-100 border border-neutral-200 rounded-lg text-xs text-neutral-800">
      {{ importMessage }}
    </div>

    <!-- Deadzone Range Adjuster Panel -->
    <div v-if="recalculatedPoints.length > 0" data-tour="analysis-range" class="p-5 bg-white border border-neutral-200/80 rounded-xl space-y-4 shadow-xs">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-neutral-100 pb-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
            <Sliders class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">
              {{ t('deadzone_filter_title') }}
            </h3>
            <p class="text-[11px] text-neutral-400">
              {{ t('effective_detection_range') }}
            </p>
          </div>
        </div>
        <div class="flex items-center space-x-2">
          <button
            type="button"
            @click="resetDeadzoneRange(0.0, 1.0)"
            class="px-2.5 py-1 rounded bg-neutral-100 hover:bg-neutral-200 text-[11px] font-medium text-neutral-700 transition cursor-pointer"
          >
            {{ t('reset_full') }}
          </button>
          <button
            type="button"
            @click="resetDeadzoneRange(sessionStore.config?.inner_deadzone || 0.0, sessionStore.config?.outer_deadzone || 1.0)"
            class="px-2.5 py-1 rounded bg-neutral-100 hover:bg-neutral-200 text-[11px] font-medium text-neutral-700 transition cursor-pointer"
          >
            {{ t('apply_calibrated') }} ({{ ((sessionStore.config?.inner_deadzone || 0) * 100).toFixed(1) }}% ~ {{ ((sessionStore.config?.outer_deadzone || 1) * 100).toFixed(1) }}%)
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Inner Deadzone Slider -->
        <div class="space-y-2 p-3.5 rounded-xl bg-neutral-50 border border-neutral-200/70">
          <div class="flex items-center justify-between">
            <label class="text-xs font-medium text-neutral-700">{{ t('inner_cutoff') }}</label>
            <span class="text-xs font-mono font-bold text-neutral-900">
              {{ (analysisInnerDeadzone * 100).toFixed(1) }}% ({{ analysisInnerDeadzone.toFixed(3) }})
            </span>
          </div>
          <input
            type="range"
            v-model.number="analysisInnerDeadzone"
            min="0.0"
            :max="Math.min(0.99, analysisOuterDeadzone - 0.01)"
            step="0.005"
            class="w-full h-1.5 bg-neutral-200 rounded-lg appearance-none cursor-pointer accent-neutral-900"
          />
        </div>

        <!-- Outer Deadzone Slider -->
        <div class="space-y-2 p-3.5 rounded-xl bg-neutral-50 border border-neutral-200/70">
          <div class="flex items-center justify-between">
            <label class="text-xs font-medium text-neutral-700">{{ t('outer_cutoff') }}</label>
            <span class="text-xs font-mono font-bold text-neutral-900">
              {{ (analysisOuterDeadzone * 100).toFixed(1) }}% ({{ analysisOuterDeadzone.toFixed(3) }})
            </span>
          </div>
          <input
            type="range"
            v-model.number="analysisOuterDeadzone"
            :min="Math.max(0.01, analysisInnerDeadzone + 0.01)"
            max="1.0"
            step="0.005"
            class="w-full h-1.5 bg-neutral-200 rounded-lg appearance-none cursor-pointer accent-neutral-900"
          />
        </div>
      </div>

      <div class="flex flex-col sm:flex-row sm:items-center justify-between text-xs font-mono text-neutral-500 pt-1 border-t border-neutral-100 gap-1">
        <div>
          {{ t('selected_range') }}: <span class="font-bold text-neutral-900">{{ (analysisInnerDeadzone * 100).toFixed(1) }}% ~ {{ (analysisOuterDeadzone * 100).toFixed(1) }}%</span>
          （{{ t('nodes_included') }} <span class="font-bold text-neutral-900">{{ recalculatedPoints.filter(p => p.in_analysis_range).length }}</span> / {{ recalculatedPoints.length }} {{ t('total_nodes') }}）
        </div>
        <div v-if="recalculatedPoints.filter(p => p.in_analysis_range && p.valid).length > 0">
          {{ t('effective_range') }}: {{ Math.min(...recalculatedPoints.filter(p => p.in_analysis_range && p.valid && p.velocity_px_s !== null).map(p => p.velocity_px_s!)).toFixed(1) }} px/s
          ➔ {{ Math.max(...recalculatedPoints.filter(p => p.in_analysis_range && p.valid && p.velocity_px_s !== null).map(p => p.velocity_px_s!)).toFixed(1) }} px/s
        </div>
      </div>
    </div>

    <!-- Main Chart Section -->
    <div data-tour="analysis-chart" class="p-5 bg-white border border-neutral-200/80 rounded-xl space-y-4 shadow-xs">
      <div class="flex items-center justify-between border-b border-neutral-100 pb-3 flex-wrap gap-2">
        <div class="flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
            <BarChart3 class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">{{ t('chart_title') }}</h3>
            <p class="text-[11px] text-neutral-400 font-mono">
              {{ recalculatedPoints.length }} {{ t('points_suffix') }}
            </p>
          </div>
        </div>
        <div class="flex items-center space-x-4 text-xs font-mono text-neutral-500">
          <span class="flex items-center space-x-1.5">
            <span class="w-3 h-0.5 bg-neutral-400 inline-block"></span>
            <span>{{ t('inner_cutoff') }}: {{ (analysisInnerDeadzone * 100).toFixed(1) }}%</span>
          </span>
          <span class="flex items-center space-x-1.5">
            <span class="w-3 h-0.5 bg-neutral-700 inline-block"></span>
            <span>{{ t('outer_cutoff') }}: {{ (analysisOuterDeadzone * 100).toFixed(1) }}%</span>
          </span>
        </div>
      </div>

      <div v-if="recalculatedPoints.length > 0">
        <CurveChart
          :points="recalculatedPoints"
          :imported-points="importedResult?.points ?? []"
          :inner-deadzone="analysisInnerDeadzone"
          :outer-deadzone="analysisOuterDeadzone"
          :fitted-curve="activeCandidate?.curvePoints"
          :breakpoints="activeCandidate?.breakpoints"
          :outlier-inputs="fitReport?.outlierInputs"
        />
      </div>
      <div v-else class="h-64 flex flex-col items-center justify-center text-neutral-400 text-xs space-y-2">
        <Activity class="w-7 h-7 text-neutral-300" />
        <span>{{ t('no_data_hint') }}</span>
      </div>
    </div>

    <!-- Data Table Breakdown -->
    <div v-if="recalculatedPoints.length > 0" class="p-5 bg-white border border-neutral-200/80 rounded-xl space-y-3 shadow-xs">
      <div class="flex items-center justify-between border-b border-neutral-100 pb-3 flex-wrap gap-2">
        <div class="flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center shrink-0">
            <FileSpreadsheet class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">{{ t('table_title') }}</h3>
            <p v-if="noise" class="text-[11px] text-neutral-400 font-mono">
              Noise Floor: X={{ noise.floor_x }} px/s, Y={{ noise.floor_y }} px/s
            </p>
          </div>
        </div>
      </div>

      <div class="max-h-60 overflow-y-auto rounded-lg border border-neutral-200">
        <table class="w-full text-left text-xs font-mono">
          <thead class="bg-neutral-100 text-neutral-600 sticky top-0">
            <tr>
              <th class="p-2">#</th>
              <th class="p-2">{{ t('stick_input') }}</th>
              <th class="p-2">{{ t('angular_velocity') }}</th>
              <th class="p-2">{{ t('normalized_speed') }}</th>
              <th class="p-2">{{ t('stability') }}</th>
              <th class="p-2">{{ t('coverage') }}</th>
              <th class="p-2">{{ t('attempts') }}</th>
              <th class="p-2">{{ t('status') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-neutral-100 text-neutral-800">
            <tr
              v-for="(pt, idx) in recalculatedPoints"
              :key="idx"
              class="transition"
              :class="[
                pt.in_analysis_range ? 'hover:bg-neutral-50' : 'bg-neutral-50/50 opacity-60 hover:opacity-100'
              ]"
            >
              <td class="p-2 text-neutral-400">{{ idx + 1 }}</td>
              <td class="p-2 font-bold">{{ (pt.input * 100).toFixed(1) }}%</td>
              <td class="p-2 font-medium">{{ pt.velocity_px_s !== null ? `${pt.velocity_px_s} px/s` : '-' }}</td>
              <td class="p-2 font-semibold" :class="pt.in_analysis_range ? 'text-neutral-900' : 'text-neutral-400'">
                {{ pt.normalized_speed !== null ? `${(pt.normalized_speed * 100).toFixed(1)}%` : '-' }}
              </td>
              <td class="p-2">{{ Math.round(pt.stability * 100) }}%</td>
              <td class="p-2">{{ Math.round(((pt as any).coverage ?? pt.stability) * 100) }}%</td>
              <td class="p-2 text-neutral-500">{{ pt.attempts }}</td>
              <td class="p-2">
                <span
                  v-if="!pt.valid"
                  class="text-rose-600 font-medium"
                >
                  {{ t('status_invalid') }}
                </span>
                <span
                  v-else-if="pt.in_analysis_range"
                  class="text-neutral-900 font-medium"
                >
                  {{ t('status_valid') }}
                </span>
                <span
                  v-else
                  class="text-neutral-400"
                >
                  {{ t('status_outside') }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
