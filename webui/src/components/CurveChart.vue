<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { init, graphic, use, type EChartsType } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import type { MeasurementPoint } from '../types/api'
import { buildVelocitySeries } from '../services/chartSeries'
import { t } from '../services/i18n'

use([LineChart, CanvasRenderer, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent])

const props = defineProps<{
  points: MeasurementPoint[]
  importedPoints?: MeasurementPoint[]
  innerDeadzone?: number
  outerDeadzone?: number
  fittedCurve?: [number, number][]
  breakpoints?: number[]
  outlierInputs?: number[]
}>()

const chartContainer = ref<HTMLDivElement | null>(null)
let chartInstance: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

// Visibility states
const selectedMap = ref<Record<string, boolean>>({})
const showMarkLines = ref(true)

function isSeriesVisible(name: string): boolean {
  return selectedMap.value[name] !== false
}

function toggleSeries(name: string) {
  const current = isSeriesVisible(name)
  selectedMap.value = {
    ...selectedMap.value,
    [name]: !current,
  }
  if (chartInstance) {
    chartInstance.dispatchAction({
      type: 'legendToggleSelect',
      name,
    })
  }
}

function toggleMarkLines() {
  showMarkLines.value = !showMarkLines.value
  updateChart()
}

function showAllSeries() {
  const updated: Record<string, boolean> = {}
  for (const k of Object.keys(selectedMap.value)) {
    updated[k] = true
  }
  selectedMap.value = updated
  showMarkLines.value = true
  if (chartInstance) {
    chartInstance.dispatchAction({
      type: 'legendAllSelect',
    })
    updateChart()
  }
}

function updateChart() {
  if (!chartInstance) return

  const velocitySeries = buildVelocitySeries(props.points, props.importedPoints)
  const normalizedData = props.points.map((p) => [p.input, p.normalized_speed])

  const markLines: any[] = []
  if (showMarkLines.value) {
    if (props.innerDeadzone !== undefined && props.innerDeadzone > 0) {
      markLines.push({
        xAxis: props.innerDeadzone,
        label: {
          formatter: `${t('inner_deadzone')}: ${(props.innerDeadzone * 100).toFixed(1)}%`,
          color: '#525252',
          fontSize: 10,
          position: 'insideEndTop',
        },
        lineStyle: {
          color: '#737373',
          type: 'dashed',
          width: 1.5,
        },
      })
    }
    if (props.outerDeadzone !== undefined && props.outerDeadzone < 1.0) {
      markLines.push({
        xAxis: props.outerDeadzone,
        label: {
          formatter: `${t('outer_deadzone')}: ${(props.outerDeadzone * 100).toFixed(1)}%`,
          color: '#525252',
          fontSize: 10,
          position: 'insideEndTop',
        },
        lineStyle: {
          color: '#525252',
          type: 'dashed',
          width: 1.5,
        },
      })
    }

    // Breakpoints Marklines (Light blue dashed)
    if (props.breakpoints && props.breakpoints.length > 0) {
      for (const bp of props.breakpoints) {
        markLines.push({
          xAxis: bp,
          label: {
            formatter: `${t('breakpoint_accel_label')}: ${(bp * 100).toFixed(1)}%`,
            color: '#0284c7',
            fontSize: 10,
            position: 'insideEndTop',
          },
          lineStyle: {
            color: '#38bdf8',
            type: 'dashed',
            width: 1.5,
          },
        })
      }
    }
  }

  const isFittedCurveActive = props.fittedCurve && props.fittedCurve.length > 0
  const legendItems = [...velocitySeries.map((series) => series.name)]
  if (isFittedCurveActive) {
    legendItems.push(t('series_fitted_curve'))
  }
  legendItems.push(t('series_normalized'))

  // Initialize selectedMap keys if not already present
  for (const item of legendItems) {
    if (selectedMap.value[item] === undefined) {
      selectedMap.value[item] = true
    }
  }

  const option: any = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#e5e7eb',
      borderWidth: 1,
      extraCssText: 'box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); border-radius: 8px;',
      textStyle: { color: '#171717', fontSize: 12 },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        const xVal = params[0].value[0]
        const pt = props.points.find((p) => Math.abs(p.input - xVal) < 1e-4)
        const isOutlier = props.outlierInputs?.some((outX) => Math.abs(outX - xVal) < 1e-3)

        let html = `<div class="font-medium text-neutral-900 mb-1 border-b border-neutral-100 pb-1 flex items-center justify-between gap-2">
          <span>${t('chart_tooltip_input')}: ${(xVal * 100).toFixed(1)}%</span>
          ${isOutlier ? `<span class="text-[10px] text-neutral-500 bg-neutral-100 px-1.5 py-0.5 rounded font-normal">${t('outlier_point_tag')}</span>` : ''}
        </div>`

        // Highlight fitted curve speed if active
        const fittedParam = params.find((p: any) => p.seriesName === t('series_fitted_curve'))
        if (fittedParam && fittedParam.value) {
          html += `<div class="flex justify-between space-x-4 text-xs mb-0.5"><span class="text-sky-600 font-medium">${t('series_fitted_curve')}:</span> <span class="font-mono font-medium text-sky-600">${Math.round(fittedParam.value[1])} px/s</span></div>`
        }

        if (pt) {
          if (pt.valid && pt.velocity_px_s !== null) {
            html += `<div class="flex justify-between space-x-4 text-xs"><span class="text-neutral-500">${t('chart_tooltip_velocity')}:</span> <span class="font-mono font-medium text-neutral-900">${pt.velocity_px_s} px/s</span></div>`
            if (pt.normalized_speed !== null) {
              html += `<div class="flex justify-between space-x-4 text-xs"><span class="text-neutral-500">${t('chart_tooltip_normalized')}:</span> <span class="font-mono text-neutral-900">${(pt.normalized_speed * 100).toFixed(1)}%</span></div>`
            }
            html += `<div class="flex justify-between space-x-4 text-xs"><span class="text-neutral-400">${t('chart_tooltip_stability')}:</span> <span class="font-mono text-neutral-600">${Math.round(pt.stability * 100)}%</span></div>`
          } else {
            html += `<div class="text-neutral-500 text-xs font-medium">${t('chart_tooltip_invalid')}</div>`
          }
        }
        return html
      },
    },
    legend: {
      show: true,
      data: legendItems,
      selected: { ...selectedMap.value },
      textStyle: { color: '#525252', fontSize: 11 },
      top: 4,
      left: 'center', // Centered to avoid colliding with left/right axis names
      itemGap: 16,
      itemWidth: 16,
      itemHeight: 8,
      cursor: 'pointer',
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '8%',
      top: '16%',
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      min: 0.0,
      max: 1.0,
      name: t('chart_axis_input'),
      nameLocation: 'middle',
      nameGap: 24,
      nameTextStyle: { color: '#737373', fontSize: 11 },
      axisLabel: {
        color: '#737373',
        fontSize: 10,
        formatter: (val: number) => `${Math.round(val * 100)}%`,
      },
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
      axisLine: { lineStyle: { color: '#e5e7eb' } },
    },
    yAxis: [
      {
        type: 'value',
        name: t('chart_axis_velocity'),
        position: 'left',
        nameLocation: 'end',
        nameTextStyle: { color: '#171717', fontSize: 11, align: 'left', padding: [0, 0, 6, 0] },
        axisLabel: { color: '#737373', fontSize: 10 },
        splitLine: { lineStyle: { color: '#f0f0f0' } },
        axisLine: { lineStyle: { color: '#e5e7eb' } },
      },
      {
        type: 'value',
        name: t('chart_axis_normalized'),
        min: 0,
        max: 1,
        position: 'right',
        nameLocation: 'end',
        nameTextStyle: { color: '#737373', fontSize: 11, align: 'right', padding: [0, 0, 6, 0] },
        axisLabel: {
          color: '#737373',
          fontSize: 10,
          formatter: (val: number) => `${Math.round(val * 100)}%`,
        },
        splitLine: { show: false },
        axisLine: { lineStyle: { color: '#e5e7eb' } },
      },
    ],
    series: [
      ...velocitySeries.map((series) => ({
        name: series.name,
        type: 'line',
        yAxisIndex: 0,
        data: series.data,
        smooth: 0.2,
        showSymbol: true,
        symbolSize: 5,
        itemStyle: { color: series.imported ? '#737373' : '#171717' },
        lineStyle: { width: series.imported ? 1.5 : 1.5, type: series.imported ? 'dashed' : 'solid', color: series.imported ? '#737373' : '#737373' },
        areaStyle: series.imported ? undefined : {
          color: new graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 0, 0, 0.03)' },
            { offset: 1, color: 'rgba(0, 0, 0, 0.0)' },
          ]),
        },
      })),
      ...(isFittedCurveActive
        ? [
            {
              name: t('series_fitted_curve'),
              type: 'line',
              yAxisIndex: 0,
              data: props.fittedCurve,
              smooth: true,
              showSymbol: false,
              z: 5,
              itemStyle: { color: '#38bdf8' },
              lineStyle: {
                width: 2.5,
                color: '#38bdf8', // 浅蓝色
              },
            },
          ]
        : []),
      {
        name: t('series_normalized'),
        type: 'line',
        yAxisIndex: 1,
        data: normalizedData,
        smooth: false,
        showSymbol: false,
        itemStyle: { color: '#a3a3a3' },
        lineStyle: { width: 1.5, type: 'dashed', color: '#a3a3a3' },
      },
      // Independent markline host series so marklines remain visible regardless of which series is toggled
      {
        name: '__auxiliary_marklines__',
        type: 'line',
        yAxisIndex: 0,
        data: [],
        silent: true,
        showSymbol: false,
        markLine: markLines.length > 0 ? { data: markLines, symbol: 'none' } : undefined,
      },
    ],
  }

  chartInstance.setOption(option)
}

onMounted(() => {
  if (chartContainer.value) {
    chartInstance = init(chartContainer.value)
    
    // Sync legend clicks with reactive selectedMap
    chartInstance.on('legendselectchanged', (event: any) => {
      if (event.selected) {
        selectedMap.value = { ...selectedMap.value, ...event.selected }
      }
    })

    updateChart()

    resizeObserver = new ResizeObserver(() => {
      chartInstance?.resize()
    })
    resizeObserver.observe(chartContainer.value)
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  chartInstance?.dispose()
  chartInstance = null
})

watch(
  () => [
    props.points,
    props.importedPoints,
    props.innerDeadzone,
    props.outerDeadzone,
    props.fittedCurve,
    props.breakpoints,
    props.outlierInputs,
  ],
  () => {
    updateChart()
  },
  { deep: true }
)
</script>

<template>
  <div class="w-full space-y-2">
    <!-- Interactive Curve/Data Display Toggle Bar -->
    <div class="flex items-center justify-between flex-wrap gap-2 px-1 text-xs">
      <div class="flex items-center space-x-1.5 flex-wrap gap-y-1">
        <span class="text-neutral-400 text-[11px] font-medium mr-1">{{ t('chart_display_toggle') }}:</span>

        <!-- 实测速度 (px/s) -->
        <button
          type="button"
          @click="toggleSeries(t('series_measured'))"
          :class="[
            'px-2.5 py-1 rounded-md text-[11px] font-medium transition-all flex items-center space-x-1.5 cursor-pointer border',
            isSeriesVisible(t('series_measured'))
              ? 'bg-neutral-900 text-white border-neutral-900 shadow-xs'
              : 'bg-neutral-100 text-neutral-400 border-neutral-200 line-through opacity-60 hover:opacity-100'
          ]"
        >
          <span class="w-1.5 h-1.5 rounded-full" :class="isSeriesVisible(t('series_measured')) ? 'bg-white' : 'bg-neutral-400'"></span>
          <span>{{ t('series_measured') }}</span>
        </button>

        <!-- 导入速度 (px/s) (如果有导入对比数据) -->
        <button
          v-if="importedPoints && importedPoints.length > 0"
          type="button"
          @click="toggleSeries(t('series_imported'))"
          :class="[
            'px-2.5 py-1 rounded-md text-[11px] font-medium transition-all flex items-center space-x-1.5 cursor-pointer border',
            isSeriesVisible(t('series_imported'))
              ? 'bg-neutral-700 text-white border-neutral-700 shadow-xs'
              : 'bg-neutral-100 text-neutral-400 border-neutral-200 line-through opacity-60 hover:opacity-100'
          ]"
        >
          <span class="w-1.5 h-1.5 rounded-full" :class="isSeriesVisible(t('series_imported')) ? 'bg-white' : 'bg-neutral-400'"></span>
          <span>{{ t('series_imported') }}</span>
        </button>

        <!-- 估算拟合曲线 (浅蓝色) -->
        <button
          v-if="fittedCurve && fittedCurve.length > 0"
          type="button"
          @click="toggleSeries(t('series_fitted_curve'))"
          :class="[
            'px-2.5 py-1 rounded-md text-[11px] font-medium transition-all flex items-center space-x-1.5 cursor-pointer border',
            isSeriesVisible(t('series_fitted_curve'))
              ? 'bg-sky-500 text-white border-sky-500 shadow-xs'
              : 'bg-neutral-100 text-neutral-400 border-neutral-200 line-through opacity-60 hover:opacity-100'
          ]"
        >
          <span class="w-1.5 h-1.5 rounded-full" :class="isSeriesVisible(t('series_fitted_curve')) ? 'bg-white' : 'bg-neutral-400'"></span>
          <span>{{ t('series_fitted_curve') }}</span>
        </button>

        <!-- 归一化响应 -->
        <button
          type="button"
          @click="toggleSeries(t('series_normalized'))"
          :class="[
            'px-2.5 py-1 rounded-md text-[11px] font-medium transition-all flex items-center space-x-1.5 cursor-pointer border',
            isSeriesVisible(t('series_normalized'))
              ? 'bg-neutral-500 text-white border-neutral-500 shadow-xs'
              : 'bg-neutral-100 text-neutral-400 border-neutral-200 line-through opacity-60 hover:opacity-100'
          ]"
        >
          <span class="w-1.5 h-1.5 rounded-full" :class="isSeriesVisible(t('series_normalized')) ? 'bg-white' : 'bg-neutral-400'"></span>
          <span>{{ t('series_normalized') }}</span>
        </button>

        <!-- 标线显隐 -->
        <button
          type="button"
          @click="toggleMarkLines"
          :class="[
            'px-2.5 py-1 rounded-md text-[11px] font-medium transition-all flex items-center space-x-1.5 cursor-pointer border',
            showMarkLines
              ? 'bg-neutral-100 text-neutral-800 border-neutral-300 font-semibold shadow-xs'
              : 'bg-neutral-100 text-neutral-400 border-neutral-200 line-through opacity-60 hover:opacity-100'
          ]"
        >
          <span>{{ t('toggle_marklines') }}</span>
        </button>
      </div>

      <!-- 全部显示快捷按钮 -->
      <button
        type="button"
        @click="showAllSeries"
        class="text-[11px] text-neutral-400 hover:text-neutral-800 cursor-pointer underline underline-offset-2 transition-colors font-medium"
      >
        {{ t('show_all_curves') }}
      </button>
    </div>

    <!-- Chart Canvas Container -->
    <div ref="chartContainer" class="w-full h-80 sm:h-96"></div>
  </div>
</template>
