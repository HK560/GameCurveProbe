<script setup lang="ts">
import { computed } from 'vue'
import type { RoiQuality } from '../types/api'
import { CheckCircle2, AlertTriangle, AlertCircle, Sparkles } from 'lucide-vue-next'

const props = defineProps<{
  quality: RoiQuality | null
}>()

const levelConfig = computed(() => {
  if (!props.quality) {
    return {
      text: '未分析',
      bg: 'bg-slate-800',
      border: 'border-slate-700',
      textCol: 'text-slate-400',
      icon: AlertCircle,
    }
  }
  switch (props.quality.level) {
    case 'excellent':
      return {
        text: '极佳特征',
        bg: 'bg-indigo-950/80',
        border: 'border-indigo-500/60',
        textCol: 'text-indigo-300',
        icon: Sparkles,
      }
    case 'good':
      return {
        text: '良好特征',
        bg: 'bg-emerald-950/80',
        border: 'border-emerald-500/60',
        textCol: 'text-emerald-300',
        icon: CheckCircle2,
      }
    case 'fair':
      return {
        text: '一般特征',
        bg: 'bg-amber-950/80',
        border: 'border-amber-500/60',
        textCol: 'text-amber-300',
        icon: AlertTriangle,
      }
    case 'poor':
    default:
      return {
        text: '质量较差',
        bg: 'bg-rose-950/80',
        border: 'border-rose-500/60',
        textCol: 'text-rose-300',
        icon: AlertCircle,
      }
  }
})

const suggestionTextMap: Record<string, string> = {
  ROI_TOO_SMALL: '选区尺寸小于 32x32 像素，过小无法稳定追踪',
  REGION_TOO_FLAT: '区域图像过于平坦（缺乏对比度），请避开纯色天空或暗角',
  FEW_FEATURE_POINTS: '角点特征不足，建议选区包含清晰几何边缘、UI或建筑边缘',
  LOW_HORIZONTAL_TEXTURE: '水平纹理不足，建议选取具有明显纵横纹理对比的区域',
}
</script>

<template>
  <div v-if="quality" class="p-4 rounded-xl border" :class="[levelConfig.bg, levelConfig.border]">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center space-x-2">
        <component :is="levelConfig.icon" class="w-5 h-5" :class="levelConfig.textCol" />
        <span class="font-semibold text-sm" :class="levelConfig.textCol">{{ levelConfig.text }}</span>
      </div>
      <div class="flex items-baseline space-x-1">
        <span class="text-2xl font-bold font-mono" :class="levelConfig.textCol">{{ quality.score }}</span>
        <span class="text-xs text-slate-400">/ 100 分</span>
      </div>
    </div>

    <!-- Metrics Progress -->
    <div class="grid grid-cols-2 gap-2 text-xs text-slate-300 mb-3">
      <div>
        <div class="flex justify-between mb-1">
          <span class="text-slate-400">梯度丰富度</span>
          <span>{{ Math.round((quality.metrics.gradient || 0) * 100) }}%</span>
        </div>
        <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div class="bg-indigo-500 h-full rounded-full transition-all duration-300" :style="{ width: `${(quality.metrics.gradient || 0) * 100}%` }"></div>
        </div>
      </div>
      <div>
        <div class="flex justify-between mb-1">
          <span class="text-slate-400">角点特征数</span>
          <span>{{ Math.round((quality.metrics.corners || 0) * 100) }}%</span>
        </div>
        <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div class="bg-emerald-500 h-full rounded-full transition-all duration-300" :style="{ width: `${(quality.metrics.corners || 0) * 100}%` }"></div>
        </div>
      </div>
      <div>
        <div class="flex justify-between mb-1">
          <span class="text-slate-400">纹理信息熵</span>
          <span>{{ Math.round((quality.metrics.entropy || 0) * 100) }}%</span>
        </div>
        <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div class="bg-cyan-500 h-full rounded-full transition-all duration-300" :style="{ width: `${(quality.metrics.entropy || 0) * 100}%` }"></div>
        </div>
      </div>
      <div>
        <div class="flex justify-between mb-1">
          <span class="text-slate-400">水平追踪匹配</span>
          <span>{{ Math.round((quality.metrics.tracking || 0) * 100) }}%</span>
        </div>
        <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div class="bg-purple-500 h-full rounded-full transition-all duration-300" :style="{ width: `${(quality.metrics.tracking || 0) * 100}%` }"></div>
        </div>
      </div>
    </div>

    <!-- Suggestions -->
    <div v-if="quality.suggestions && quality.suggestions.length > 0" class="space-y-1 mt-2 pt-2 border-t border-slate-800/80">
      <div v-for="sug in quality.suggestions" :key="sug" class="flex items-start space-x-1.5 text-xs text-amber-300/90">
        <span class="text-amber-400 font-bold">•</span>
        <span>{{ suggestionTextMap[sug] || sug }}</span>
      </div>
    </div>
  </div>
  <div v-else class="p-4 rounded-xl border border-slate-800 bg-slate-900/40 text-center text-xs text-slate-500">
    在画面上拖拽鼠标框选 ROI 区域以评估追踪质量
  </div>
</template>
