<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { init, graphic, use, type EChartsType } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import type { MeasurementPoint } from '../types/api'
import { buildVelocitySeries } from '../services/chartSeries'

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
        formatter: `内死区: ${(props.innerDeadzone * 100).toFixed(1)}%`,
        color: '#f59e0b',
        position: 'insideEndTop',
      },
      lineStyle: {
        color: '#f59e0b',
        type: 'dashed',
        width: 1.5,
      },
    })
  }
  if (props.outerDeadzone !== undefined && props.outerDeadzone < 1.0) {
    markLines.push({
      xAxis: props.outerDeadzone,
      label: {
        formatter: `外死区: ${(props.outerDeadzone * 100).toFixed(1)}%`,
        color: '#a855f7',
        position: 'insideEndTop',
      },
      lineStyle: {
        color: '#a855f7',
        type: 'dashed',
        width: 1.5,
      },
    })
  }

  const option: any = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: '#334155',
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        const xVal = params[0].value[0]
        const pt = props.points.find((p) => Math.abs(p.input - xVal) < 1e-4)
        let html = `<div class="font-bold text-slate-200 mb-1">摇杆推杆量: ${(xVal * 100).toFixed(1)}% (${xVal.toFixed(3)})</div>`
        if (pt) {
          if (pt.valid && pt.velocity_px_s !== null) {
            html += `<div class="flex justify-between space-x-4"><span class="text-indigo-400">测定速度:</span> <span class="font-mono font-bold">${pt.velocity_px_s} px/s</span></div>`
            if (pt.normalized_speed !== null) {
              html += `<div class="flex justify-between space-x-4"><span class="text-emerald-400">归一化比例:</span> <span class="font-mono">${(pt.normalized_speed * 100).toFixed(1)}%</span></div>`
            }
            html += `<div class="flex justify-between space-x-4"><span class="text-slate-400">稳定性评分:</span> <span class="font-mono">${Math.round(pt.stability * 100)}%</span></div>`
          } else {
            html += `<div class="text-rose-400 font-semibold">该点追踪无效 (特征丢失或环境扰动)</div>`
          }
        }
        return html
      },
    },
    legend: {
      data: [...velocitySeries.map((series) => series.name), '归一化响应'],
      textStyle: { color: '#94a3b8' },
      top: 0,
      right: 16,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '8%',
      top: '12%',
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      min: 0.0,
      max: 1.0,
      name: '推杆行程',
      nameLocation: 'middle',
      nameGap: 24,
      nameTextStyle: { color: '#64748b', fontSize: 11 },
      axisLabel: {
        color: '#94a3b8',
        formatter: (val: number) => `${Math.round(val * 100)}%`,
      },
      splitLine: { lineStyle: { color: 'rgba(51, 65, 85, 0.4)', type: 'dashed' } },
      axisLine: { lineStyle: { color: '#475569' } },
    },
    yAxis: [
      {
        type: 'value',
        name: '速度 (px/s)',
        position: 'left',
        nameTextStyle: { color: '#818cf8', fontSize: 11 },
        axisLabel: { color: '#818cf8' },
        splitLine: { lineStyle: { color: 'rgba(51, 65, 85, 0.3)' } },
        axisLine: { lineStyle: { color: '#475569' } },
      },
      {
        type: 'value',
        name: '归一化比例',
        min: 0,
        max: 1,
        position: 'right',
        nameTextStyle: { color: '#34d399', fontSize: 11 },
        axisLabel: {
          color: '#34d399',
          formatter: (val: number) => `${Math.round(val * 100)}%`,
        },
        splitLine: { show: false },
        axisLine: { lineStyle: { color: '#475569' } },
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
        symbolSize: 6,
        itemStyle: { color: series.imported ? '#f59e0b' : '#6366f1' },
        lineStyle: { width: series.imported ? 2 : 3, type: series.imported ? 'dashed' : 'solid', color: series.imported ? '#f59e0b' : '#6366f1' },
        areaStyle: series.imported ? undefined : {
          color: new graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(99, 102, 241, 0.35)' },
            { offset: 1, color: 'rgba(99, 102, 241, 0.0)' },
          ]),
        },
        markLine: markLines.length > 0 ? { data: markLines, symbol: 'none' } : undefined,
      })),
      {
        name: '归一化响应',
        type: 'line',
        yAxisIndex: 1,
        data: normalizedData,
        smooth: false,
        showSymbol: false,
        itemStyle: { color: '#10b981' },
        lineStyle: { width: 1.5, type: 'dashed', color: '#10b981' },
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
