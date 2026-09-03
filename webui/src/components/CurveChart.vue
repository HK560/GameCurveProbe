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
}>()

const chartContainer = ref<HTMLDivElement | null>(null)
let chartInstance: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

function updateChart() {
  if (!chartInstance) return

  const velocitySeries = buildVelocitySeries(props.points, props.importedPoints)
  const normalizedData = props.points.map((p) => [p.input, p.normalized_speed])

  const markLines: any[] = []
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
        let html = `<div class="font-medium text-neutral-900 mb-1 border-b border-neutral-100 pb-1">${t('chart_tooltip_input')}: ${(xVal * 100).toFixed(1)}% (${xVal.toFixed(3)})</div>`
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
      data: [...velocitySeries.map((series) => series.name), t('series_normalized')],
      textStyle: { color: '#737373', fontSize: 11 },
      top: 0,
      right: 16,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '8%',
      top: '14%',
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
        nameTextStyle: { color: '#171717', fontSize: 11 },
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
        nameTextStyle: { color: '#737373', fontSize: 11 },
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
        lineStyle: { width: series.imported ? 2 : 2.5, type: series.imported ? 'dashed' : 'solid', color: series.imported ? '#737373' : '#171717' },
        areaStyle: series.imported ? undefined : {
          color: new graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 0, 0, 0.05)' },
            { offset: 1, color: 'rgba(0, 0, 0, 0.0)' },
          ]),
        },
        markLine: markLines.length > 0 ? { data: markLines, symbol: 'none' } : undefined,
      })),
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
    ],
  }

  chartInstance.setOption(option)
}

onMounted(() => {
  if (chartContainer.value) {
    chartInstance = init(chartContainer.value)
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
  () => [props.points, props.importedPoints, props.innerDeadzone, props.outerDeadzone],
  () => {
    updateChart()
  },
  { deep: true }
)
</script>

<template>
  <div ref="chartContainer" class="w-full h-80 sm:h-96"></div>
</template>
