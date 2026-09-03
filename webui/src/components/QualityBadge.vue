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
      textCol: 'text-neutral-500',
      icon: AlertCircle,
    }
  }
  switch (props.quality.level) {
    case 'excellent':
      return {
        text: '极佳特征',
        textCol: 'text-neutral-900',
        icon: Sparkles,
      }
    case 'good':
      return {
        text: '良好特征',
        textCol: 'text-neutral-800',
        icon: CheckCircle2,
      }
    case 'fair':
      return {
        text: '一般特征',
        textCol: 'text-neutral-700',
        icon: AlertTriangle,
      }
    case 'poor':
    default:
      return {
        text: '质量较差',
        textCol: 'text-neutral-900',
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
  <div v-if="quality" class="p-4 rounded-xl border border-neutral-200/80 bg-white">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center space-x-2">
        <component :is="levelConfig.icon" class="w-4 h-4 text-neutral-800" />
        <span class="font-medium text-xs text-neutral-900">{{ levelConfig.text }}</span>
      </div>
      <div class="flex items-baseline space-x-1">
        <span class="text-xl font-bold font-mono text-neutral-900">{{ quality.score }}</span>
        <span class="text-xs text-neutral-400">/ 100 分</span>
      </div>
    </div>

    <!-- Metrics Progress -->
    <div class="grid grid-cols-2 gap-3 text-xs text-neutral-600 mb-3">
      <div>
        <div class="flex justify-between mb-1 text-[11px]">
          <span class="text-neutral-500">梯度丰富度</span>
          <span class="font-mono text-neutral-800">{{ Math.round((quality.metrics.gradient || 0) * 100) }}%</span>
        </div>
        <div class="w-full bg-neutral-100 rounded-full h-1 overflow-hidden">
          <div class="bg-neutral-800 h-full rounded-full transition-all duration-300" :style="{ width: `${(quality.metrics.gradient || 0) * 100}%` }"></div>
        </div>
      </div>
      <div>
        <div class="flex justify-between mb-1 text-[11px]">
          <span class="text-neutral-500">角点特征数</span>
          <span class="font-mono text-neutral-800">{{ Math.round((quality.metrics.corners || 0) * 100) }}%</span>
        </div>
        <div class="w-full bg-neutral-100 rounded-full h-1 overflow-hidden">
          <div class="bg-neutral-800 h-full rounded-full transition-all duration-300" :style="{ width: `${(quality.metrics.corners || 0) * 100}%` }"></div>
        </div>
      </div>
      <div>
        <div class="flex justify-between mb-1 text-[11px]">
          <span class="text-neutral-500">纹理信息熵</span>
          <span class="font-mono text-neutral-800">{{ Math.round((quality.metrics.entropy || 0) * 100) }}%</span>
        </div>
        <div class="w-full bg-neutral-100 rounded-full h-1 overflow-hidden">
          <div class="bg-neutral-800 h-full rounded-full transition-all duration-300" :style="{ width: `${(quality.metrics.entropy || 0) * 100}%` }"></div>
        </div>
      </div>
      <div>
        <div class="flex justify-between mb-1 text-[11px]">
          <span class="text-neutral-500">水平追踪匹配</span>
          <span class="font-mono text-neutral-800">{{ Math.round((quality.metrics.tracking || 0) * 100) }}%</span>
        </div>
        <div class="w-full bg-neutral-100 rounded-full h-1 overflow-hidden">
          <div class="bg-neutral-800 h-full rounded-full transition-all duration-300" :style="{ width: `${(quality.metrics.tracking || 0) * 100}%` }"></div>
        </div>
      </div>
    </div>

    <!-- Suggestions -->
    <div v-if="quality.suggestions && quality.suggestions.length > 0" class="space-y-1 mt-2 pt-2 border-t border-neutral-100">
      <div v-for="sug in quality.suggestions" :key="sug" class="flex items-start space-x-1.5 text-xs text-neutral-600">
        <span class="text-neutral-400 font-bold">•</span>
        <span>{{ suggestionTextMap[sug] || sug }}</span>
      </div>
    </div>
  </div>
  <div v-else class="p-4 rounded-xl border border-dashed border-neutral-200 bg-neutral-50 text-center text-xs text-neutral-400">
    在画面上拖拽鼠标框选 ROI 区域以评估追踪质量
  </div>
</template>
