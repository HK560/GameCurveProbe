<script setup lang="ts">
import { computed } from 'vue'
import type { RoiQuality } from '../types/api'
import { CheckCircle2, AlertTriangle, AlertCircle, Sparkles } from 'lucide-vue-next'
import { t } from '../services/i18n'

const props = defineProps<{
  quality: RoiQuality | null
}>()

const levelConfig = computed(() => {
  if (!props.quality) {
    return {
      text: t('roi_not_analyzed'),
      textCol: 'text-neutral-500',
      icon: AlertCircle,
    }
  }
  switch (props.quality.level) {
    case 'excellent':
      return {
        text: t('roi_quality_excellent'),
        textCol: 'text-neutral-900',
        icon: Sparkles,
      }
    case 'good':
      return {
        text: t('roi_quality_good'),
        textCol: 'text-neutral-800',
        icon: CheckCircle2,
      }
    case 'fair':
      return {
        text: t('roi_quality_fair'),
        textCol: 'text-neutral-700',
        icon: AlertTriangle,
      }
    case 'poor':
    default:
      return {
        text: t('roi_quality_poor'),
        textCol: 'text-neutral-900',
        icon: AlertCircle,
      }
  }
})

const getSuggestionText = (sug: string) => {
  switch (sug) {
    case 'ROI_TOO_SMALL': return t('roi_too_small')
    case 'REGION_TOO_FLAT': return t('region_too_flat')
    case 'FEW_FEATURE_POINTS': return t('few_feature_points')
    case 'LOW_HORIZONTAL_TEXTURE': return t('low_horizontal_texture')
    default: return sug
  }
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
        <span class="text-xs text-neutral-400">/ 100</span>
      </div>
    </div>

    <!-- Metrics Progress -->
    <div class="grid grid-cols-2 gap-3 text-xs text-neutral-600 mb-3">
      <div>
        <div class="flex justify-between mb-1 text-[11px]">
          <span class="text-neutral-500">{{ t('roi_gradient') }}</span>
          <span class="font-mono text-neutral-800">{{ Math.round((quality.metrics.gradient || 0) * 100) }}%</span>
        </div>
        <div class="w-full bg-neutral-100 rounded-full h-1 overflow-hidden">
          <div class="bg-neutral-800 h-full rounded-full transition-all duration-300" :style="{ width: `${(quality.metrics.gradient || 0) * 100}%` }"></div>
        </div>
      </div>
      <div>
        <div class="flex justify-between mb-1 text-[11px]">
          <span class="text-neutral-500">{{ t('roi_corners') }}</span>
          <span class="font-mono text-neutral-800">{{ Math.round((quality.metrics.corners || 0) * 100) }}%</span>
        </div>
        <div class="w-full bg-neutral-100 rounded-full h-1 overflow-hidden">
          <div class="bg-neutral-800 h-full rounded-full transition-all duration-300" :style="{ width: `${(quality.metrics.corners || 0) * 100}%` }"></div>
        </div>
      </div>
      <div>
        <div class="flex justify-between mb-1 text-[11px]">
          <span class="text-neutral-500">{{ t('roi_entropy') }}</span>
          <span class="font-mono text-neutral-800">{{ Math.round((quality.metrics.entropy || 0) * 100) }}%</span>
        </div>
        <div class="w-full bg-neutral-100 rounded-full h-1 overflow-hidden">
          <div class="bg-neutral-800 h-full rounded-full transition-all duration-300" :style="{ width: `${(quality.metrics.entropy || 0) * 100}%` }"></div>
        </div>
      </div>
      <div>
        <div class="flex justify-between mb-1 text-[11px]">
          <span class="text-neutral-500">{{ t('roi_tracking') }}</span>
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
        <span>{{ getSuggestionText(sug) }}</span>
      </div>
    </div>
  </div>
  <div v-else class="p-4 rounded-xl border border-dashed border-neutral-200 bg-neutral-50 text-center text-xs text-neutral-400">
    {{ t('roi_instruction') }}
  </div>
</template>
