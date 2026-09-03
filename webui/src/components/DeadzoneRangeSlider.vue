<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import { t } from '../services/i18n'
import { 
  Minus, 
  Plus, 
  Target, 
  Sliders 
} from 'lucide-vue-next'
import type { RangeMode } from '../types/api'

const props = withDefaults(
  defineProps<{
    innerDeadzone: number
    outerDeadzone: number
    pointCount?: number
    rangeMode?: RangeMode
    probeActive?: boolean
    activeProbeTarget?: 'inner' | 'outer'
    step?: number
  }>(),
  {
    pointCount: 17,
    rangeMode: 'active_range',
    probeActive: false,
    activeProbeTarget: 'inner',
    step: 0.005,
  }
)

const emit = defineEmits<{
  (e: 'update:innerDeadzone', val: number): void
  (e: 'update:outerDeadzone', val: number): void
  (e: 'update:pointCount', count: number): void
  (e: 'update:rangeMode', mode: RangeMode): void
  (e: 'update:activeProbeTarget', target: 'inner' | 'outer'): void
  (e: 'probeOutput', val: number): void
}>()

const railRef = ref<HTMLElement | null>(null)
const dragging = ref<'inner' | 'outer' | null>(null)
const hoveredPointIndex = ref<number | null>(null)

// Ensure valid deadzone bounds
const safeInner = computed(() => Math.max(0.0, Math.min(props.innerDeadzone, 0.99)))
const safeOuter = computed(() => Math.max(safeInner.value + 0.01, Math.min(props.outerDeadzone, 1.0)))
const activeSpan = computed(() => Math.max(0.0, safeOuter.value - safeInner.value))

// Sampling points calculation (matches backend ProbeConfig.point_values)
const samplingPoints = computed<number[]>(() => {
  const count = props.pointCount || 17
  const mode = props.rangeMode || 'active_range'
  const start = mode === 'full' ? 0.0 : safeInner.value
  const end = mode === 'full' ? 1.0 : safeOuter.value
  const span = end - start

  const set = new Set<number>()
  for (let i = 0; i < count; i++) {
    const val = Number((start + (span * i) / (count - 1)).toFixed(4))
    set.add(val)
  }

  if (mode === 'full') {
    set.add(Number(safeInner.value.toFixed(4)))
    set.add(Number(safeOuter.value.toFixed(4)))
  }

  return Array.from(set).sort((a, b) => a - b)
})

function roundVal(v: number): number {
  return Math.round(v * 1000) / 1000
}

function adjustInner(delta: number) {
  const next = roundVal(Math.max(0.0, Math.min(safeOuter.value - 0.01, safeInner.value + delta)))
  emit('update:innerDeadzone', next)
  emit('update:activeProbeTarget', 'inner')
  if (props.probeActive) {
    emit('probeOutput', next)
  }
}

function adjustOuter(delta: number) {
  const next = roundVal(Math.max(safeInner.value + 0.01, Math.min(1.0, safeOuter.value + delta)))
  emit('update:outerDeadzone', next)
  emit('update:activeProbeTarget', 'outer')
  if (props.probeActive) {
    emit('probeOutput', next)
  }
}

function onInnerInput(e: Event) {
  const target = e.target as HTMLInputElement
  let val = parseFloat(target.value) / 100
  if (isNaN(val)) return
  val = roundVal(Math.max(0.0, Math.min(safeOuter.value - 0.01, val)))
  emit('update:innerDeadzone', val)
  if (props.probeActive && props.activeProbeTarget === 'inner') {
    emit('probeOutput', val)
  }
}

function onOuterInput(e: Event) {
  const target = e.target as HTMLInputElement
  let val = parseFloat(target.value) / 100
  if (isNaN(val)) return
  val = roundVal(Math.max(safeInner.value + 0.01, Math.min(1.0, val)))
  emit('update:outerDeadzone', val)
  if (props.probeActive && props.activeProbeTarget === 'outer') {
    emit('probeOutput', val)
  }
}

function getFractionFromPointer(e: PointerEvent | MouseEvent): number {
  if (!railRef.value) return 0
  const rect = railRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const frac = Math.max(0.0, Math.min(1.0, x / rect.width))
  return roundVal(frac)
}

function startDrag(target: 'inner' | 'outer', e: PointerEvent) {
  e.preventDefault()
  e.stopPropagation()
  dragging.value = target
  emit('update:activeProbeTarget', target)

  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
}

function onPointerMove(e: PointerEvent) {
  if (!dragging.value) return
  const frac = getFractionFromPointer(e)

  if (dragging.value === 'inner') {
    const clamped = Math.min(safeOuter.value - 0.01, Math.max(0.0, frac))
    emit('update:innerDeadzone', clamped)
    if (props.probeActive) {
      emit('probeOutput', clamped)
    }
  } else if (dragging.value === 'outer') {
    const clamped = Math.max(safeInner.value + 0.01, Math.min(1.0, frac))
    emit('update:outerDeadzone', clamped)
    if (props.probeActive) {
      emit('probeOutput', clamped)
    }
  }
}

function onPointerUp() {
  dragging.value = null
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
}

function onTrackClick(e: MouseEvent) {
  if (dragging.value) return
  const frac = getFractionFromPointer(e)
  // Closer to inner or outer?
  const distInner = Math.abs(frac - safeInner.value)
  const distOuter = Math.abs(frac - safeOuter.value)

  if (distInner <= distOuter) {
    const clamped = roundVal(Math.min(safeOuter.value - 0.01, Math.max(0.0, frac)))
    emit('update:innerDeadzone', clamped)
    emit('update:activeProbeTarget', 'inner')
    if (props.probeActive) {
      emit('probeOutput', clamped)
    }
  } else {
    const clamped = roundVal(Math.max(safeInner.value + 0.01, Math.min(1.0, frac)))
    emit('update:outerDeadzone', clamped)
    emit('update:activeProbeTarget', 'outer')
    if (props.probeActive) {
      emit('probeOutput', clamped)
    }
  }
}

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
})
</script>

<template>
  <div class="space-y-5 bg-white border border-neutral-200/80 rounded-xl p-5 shadow-xs select-none">
    <!-- Header with Active Range Badge -->
    <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
      <div class="flex items-center space-x-2.5">
        <div class="w-7 h-7 rounded-lg bg-neutral-900 text-white flex items-center justify-center">
          <Sliders class="w-4 h-4" />
        </div>
        <div>
          <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-800">
            {{ t('slider_card_title') }}
          </h3>
          <p class="text-[11px] text-neutral-400">
            {{ t('slider_card_desc') }}
          </p>
        </div>
      </div>

      <!-- Center Active Range Span Badge -->
      <div class="flex items-center space-x-2 px-3 py-1 bg-neutral-100 border border-neutral-200/60 rounded-full font-mono text-xs">
        <span class="text-neutral-500 text-[11px]">{{ t('effective_detection_range') }}:</span>
        <span class="font-bold text-neutral-900">{{ (activeSpan * 100).toFixed(1) }}%</span>
        <span class="text-[10px] text-neutral-400">({{ activeSpan.toFixed(3) }})</span>
      </div>
    </div>

    <!-- Dual Numeric Control Cards (Left: Inner, Right: Outer) -->
    <div class="grid grid-cols-2 gap-4">
      <!-- Inner Deadzone Card -->
      <div 
        @click="emit('update:activeProbeTarget', 'inner')"
        class="p-3.5 rounded-lg border transition cursor-pointer"
        :class="[
          activeProbeTarget === 'inner' 
            ? 'border-neutral-900 bg-neutral-50/80 ring-1 ring-neutral-900' 
            : 'border-neutral-200 bg-white hover:border-neutral-300'
        ]"
      >
        <div class="flex items-center justify-between mb-1.5">
          <div class="flex items-center space-x-1.5">
            <span class="w-2 h-2 rounded-full bg-neutral-900"></span>
            <span class="text-xs font-semibold text-neutral-800">{{ t('inner_deadzone') }}</span>
          </div>
          <span 
            v-if="activeProbeTarget === 'inner' && probeActive" 
            class="text-[10px] font-mono px-1.5 py-0.2 rounded bg-neutral-900 text-white"
          >
            {{ t('probe_target_badge') }}
          </span>
        </div>

        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-1">
            <input
              type="number"
              :value="(safeInner * 100).toFixed(1)"
              @input="onInnerInput"
              min="0"
              :max="(safeOuter * 100 - 1).toFixed(1)"
              step="0.1"
              class="w-20 text-2xl font-bold font-mono text-neutral-900 bg-transparent border-b border-neutral-300 focus:border-neutral-900 focus:outline-none"
            />
            <span class="text-sm font-bold font-mono text-neutral-600">%</span>
            <span class="text-xs font-mono text-neutral-400">
              ({{ safeInner.toFixed(3) }})
            </span>
          </div>

          <!-- Stepper Buttons -->
          <div class="flex items-center space-x-1">
            <button
              type="button"
              @click.stop="adjustInner(-step)"
              class="h-7 px-1.5 rounded bg-neutral-100 hover:bg-neutral-200 active:bg-neutral-300 text-neutral-700 flex items-center justify-center space-x-1 transition cursor-pointer text-xs"
              :title="t('dec_inner_deadzone')"
            >
              <Minus class="w-3.5 h-3.5" />
              <span v-if="activeProbeTarget === 'inner'" class="text-[9px] font-mono bg-neutral-200/80 px-1 rounded text-neutral-600 font-semibold">F6</span>
            </button>
            <button
              type="button"
              @click.stop="adjustInner(step)"
              class="h-7 px-1.5 rounded bg-neutral-100 hover:bg-neutral-200 active:bg-neutral-300 text-neutral-700 flex items-center justify-center space-x-1 transition cursor-pointer text-xs"
              :title="t('inc_inner_deadzone')"
            >
              <Plus class="w-3.5 h-3.5" />
              <span v-if="activeProbeTarget === 'inner'" class="text-[9px] font-mono bg-neutral-200/80 px-1 rounded text-neutral-600 font-semibold">F7</span>
            </button>
          </div>
        </div>
        <p class="text-[10px] text-neutral-400 mt-1">{{ t('inner_deadzone_desc') }}</p>
      </div>

      <!-- Outer Deadzone Card -->
      <div 
        @click="emit('update:activeProbeTarget', 'outer')"
        class="p-3.5 rounded-lg border transition cursor-pointer"
        :class="[
          activeProbeTarget === 'outer' 
            ? 'border-neutral-900 bg-neutral-50/80 ring-1 ring-neutral-900' 
            : 'border-neutral-200 bg-white hover:border-neutral-300'
        ]"
      >
        <div class="flex items-center justify-between mb-1.5">
          <div class="flex items-center space-x-1.5">
            <span class="w-2 h-2 rounded-full bg-neutral-900"></span>
            <span class="text-xs font-semibold text-neutral-800">{{ t('outer_deadzone') }}</span>
          </div>
          <span 
            v-if="activeProbeTarget === 'outer' && probeActive" 
            class="text-[10px] font-mono px-1.5 py-0.2 rounded bg-neutral-900 text-white"
          >
            {{ t('probe_target_badge') }}
          </span>
        </div>

        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-1">
            <input
              type="number"
              :value="(safeOuter * 100).toFixed(1)"
              @input="onOuterInput"
              :min="(safeInner * 100 + 1).toFixed(1)"
              max="100"
              step="0.1"
              class="w-20 text-2xl font-bold font-mono text-neutral-900 bg-transparent border-b border-neutral-300 focus:border-neutral-900 focus:outline-none"
            />
            <span class="text-sm font-bold font-mono text-neutral-600">%</span>
            <span class="text-xs font-mono text-neutral-400">
              ({{ safeOuter.toFixed(3) }})
            </span>
          </div>

          <!-- Stepper Buttons -->
          <div class="flex items-center space-x-1">
            <button
              type="button"
              @click.stop="adjustOuter(-step)"
              class="h-7 px-1.5 rounded bg-neutral-100 hover:bg-neutral-200 active:bg-neutral-300 text-neutral-700 flex items-center justify-center space-x-1 transition cursor-pointer text-xs"
              :title="t('dec_outer_deadzone')"
            >
              <Minus class="w-3.5 h-3.5" />
              <span v-if="activeProbeTarget === 'outer'" class="text-[9px] font-mono bg-neutral-200/80 px-1 rounded text-neutral-600 font-semibold">F6</span>
            </button>
            <button
              type="button"
              @click.stop="adjustOuter(step)"
              class="h-7 px-1.5 rounded bg-neutral-100 hover:bg-neutral-200 active:bg-neutral-300 text-neutral-700 flex items-center justify-center space-x-1 transition cursor-pointer text-xs"
              :title="t('inc_outer_deadzone')"
            >
              <Plus class="w-3.5 h-3.5" />
              <span v-if="activeProbeTarget === 'outer'" class="text-[9px] font-mono bg-neutral-200/80 px-1 rounded text-neutral-600 font-semibold">F7</span>
            </button>
          </div>
        </div>
        <p class="text-[10px] text-neutral-400 mt-1">{{ t('outer_deadzone_desc') }}</p>
      </div>
    </div>

    <!-- Dual-Thumb Continuous Axis Track -->
    <div class="pt-4 pb-2 px-3">
      <!-- Scale Labels Above Track -->
      <div class="flex justify-between text-[10px] font-mono text-neutral-400 mb-1.5 select-none">
        <span>0%</span>
        <span>25%</span>
        <span>50%</span>
        <span>75%</span>
        <span>100%</span>
      </div>

      <!-- Rail Container -->
      <div 
        ref="railRef"
        @click="onTrackClick"
        class="relative h-6 w-full rounded-full bg-neutral-100 border border-neutral-200 cursor-pointer overflow-visible select-none"
      >
        <!-- Region 1: Left Inactive (Inner Deadzone Blind Zone) -->
        <div 
          class="absolute left-0 top-0 bottom-0 bg-neutral-200/50 rounded-l-full flex items-center justify-center overflow-hidden"
          :style="{ width: `${safeInner * 100}%` }"
        >
          <span v-if="safeInner > 0.08" class="text-[9px] text-neutral-500 font-mono font-medium truncate px-1">
            {{ t('blind_zone') }}
          </span>
        </div>

        <!-- Region 2: Active Detection Range -->
        <div 
          class="absolute top-0 bottom-0 bg-neutral-900 shadow-sm flex items-center justify-center transition-all duration-75"
          :style="{
            left: `${safeInner * 100}%`,
            width: `${activeSpan * 100}%`
          }"
        >
          <span v-if="activeSpan > 0.15" class="text-[10px] text-white/90 font-mono font-medium tracking-wider truncate px-1">
            {{ t('detection_range_bar') }} {{ (activeSpan * 100).toFixed(1) }}%
          </span>
        </div>

        <!-- Region 3: Right Inactive (Outer Deadzone Saturation Zone) -->
        <div 
          class="absolute right-0 top-0 bottom-0 bg-neutral-200/50 rounded-r-full flex items-center justify-center overflow-hidden"
          :style="{ width: `${(1.0 - safeOuter) * 100}%` }"
        >
          <span v-if="(1.0 - safeOuter) > 0.08" class="text-[9px] text-neutral-500 font-mono font-medium truncate px-1">
            {{ t('saturation_zone') }}
          </span>
        </div>

        <!-- Predicted Sampling Point Tick Marks on Rail -->
        <div 
          v-for="(pt, idx) in samplingPoints"
          :key="idx"
          class="absolute top-1 bottom-1 w-0.5 -ml-[1px] transition-all duration-100 pointer-events-none z-10"
          :class="[
            hoveredPointIndex === idx 
              ? 'bg-amber-400 w-1 -ml-[2px] z-20' 
              : pt >= safeInner && pt <= safeOuter
                ? 'bg-neutral-100/70'
                : 'bg-neutral-400/80'
          ]"
          :style="{ left: `${pt * 100}%` }"
        >
          <!-- Small Hover Marker Dot -->
          <span 
            v-if="hoveredPointIndex === idx" 
            class="absolute -top-6 left-1/2 -translate-x-1/2 bg-neutral-900 text-white text-[9px] font-mono px-1.5 py-0.5 rounded shadow whitespace-nowrap z-30"
          >
            #{{ idx + 1 }}: {{ (pt * 100).toFixed(1) }}%
          </span>
        </div>

        <!-- Thumb 1: Inner Deadzone Handle -->
        <div
          @pointerdown="startDrag('inner', $event)"
          class="absolute top-1/2 -translate-y-1/2 -ml-3.5 w-7 h-7 rounded-full bg-white border-2 shadow-md flex items-center justify-center cursor-grab active:cursor-grabbing z-20 transition-transform duration-75 hover:scale-110"
          :class="[
            activeProbeTarget === 'inner' 
              ? 'border-neutral-900 ring-2 ring-neutral-900/30' 
              : 'border-neutral-700'
          ]"
          :style="{ left: `${safeInner * 100}%` }"
          :title="t('inner_deadzone')"
        >
          <div class="w-2.5 h-2.5 rounded-full bg-neutral-900"></div>
          <!-- Floating Label -->
          <div class="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[9px] font-mono text-neutral-600 whitespace-nowrap">
            {{ t('blind_zone') }}:{{ (safeInner * 100).toFixed(0) }}%
          </div>
        </div>

        <!-- Thumb 2: Outer Deadzone Handle -->
        <div
          @pointerdown="startDrag('outer', $event)"
          class="absolute top-1/2 -translate-y-1/2 -ml-3.5 w-7 h-7 rounded-full bg-white border-2 shadow-md flex items-center justify-center cursor-grab active:cursor-grabbing z-20 transition-transform duration-75 hover:scale-110"
          :class="[
            activeProbeTarget === 'outer' 
              ? 'border-neutral-900 ring-2 ring-neutral-900/30' 
              : 'border-neutral-700'
          ]"
          :style="{ left: `${safeOuter * 100}%` }"
          :title="t('outer_deadzone')"
        >
          <div class="w-2.5 h-2.5 rounded-full bg-neutral-900"></div>
          <!-- Floating Label -->
          <div class="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[9px] font-mono text-neutral-600 whitespace-nowrap">
            {{ t('saturation_zone') }}:{{ (safeOuter * 100).toFixed(0) }}%
          </div>
        </div>
      </div>
    </div>

    <!-- Predicted Sampling Points Details Section -->
    <div class="pt-5 border-t border-neutral-100 space-y-3">
      <div class="flex items-center justify-between flex-wrap gap-2">
        <div class="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-neutral-700">
          <Target class="w-3.5 h-3.5" />
          <span>{{ t('predicted_distribution_title') }}</span>
          <span class="text-neutral-400 font-normal font-mono text-[11px]">
            ({{ t('total_points_count') }} {{ samplingPoints.length }} {{ t('points_suffix') }})
          </span>
        </div>

        <!-- Mode & Density Controls -->
        <div class="flex items-center space-x-2">
          <!-- Range Mode Toggle -->
          <div class="flex rounded-lg bg-neutral-100 p-0.5 text-[11px] font-medium text-neutral-600">
            <button
              type="button"
              @click="emit('update:rangeMode', 'active_range')"
              class="px-2.5 py-1 rounded-md transition cursor-pointer"
              :class="rangeMode === 'active_range' ? 'bg-white text-neutral-900 shadow-xs' : 'hover:text-neutral-900'"
            >
              {{ t('active_range_sampling') }}
            </button>
            <button
              type="button"
              @click="emit('update:rangeMode', 'full')"
              class="px-2.5 py-1 rounded-md transition cursor-pointer"
              :class="rangeMode === 'full' ? 'bg-white text-neutral-900 shadow-xs' : 'hover:text-neutral-900'"
            >
              {{ t('full_range_sampling') }}
            </button>
          </div>

          <!-- Point Count Toggle -->
          <div class="flex rounded-lg bg-neutral-100 p-0.5 text-[11px] font-mono font-medium text-neutral-600">
            <button
              v-for="cnt in [9, 17, 33]"
              :key="cnt"
              type="button"
              @click="emit('update:pointCount', cnt)"
              class="px-2 py-1 rounded-md transition cursor-pointer"
              :class="pointCount === cnt ? 'bg-white text-neutral-900 shadow-xs' : 'hover:text-neutral-900'"
            >
              {{ cnt }}{{ t('points_suffix') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Point Capsule Chips Flow Grid -->
      <div class="p-3 bg-neutral-50 rounded-lg border border-neutral-200/60 max-h-40 overflow-y-auto">
        <div class="flex flex-wrap gap-1.5">
          <div
            v-for="(pt, idx) in samplingPoints"
            :key="idx"
            @mouseenter="hoveredPointIndex = idx"
            @mouseleave="hoveredPointIndex = null"
            class="px-2 py-1 rounded-md text-[11px] font-mono border transition-all cursor-default flex items-center space-x-1.5"
            :class="[
              hoveredPointIndex === idx
                ? 'bg-neutral-900 text-white border-neutral-900 shadow-xs scale-105 z-10'
                : pt === safeInner || pt === safeOuter
                  ? 'bg-white text-neutral-900 border-neutral-300 font-bold shadow-xs'
                  : 'bg-white/80 text-neutral-700 border-neutral-200 hover:border-neutral-400'
            ]"
          >
            <span class="text-neutral-400 text-[10px]" :class="{ 'text-neutral-400': hoveredPointIndex === idx }">
              #{{ idx + 1 }}
            </span>
            <span class="font-semibold">{{ pt.toFixed(3) }}</span>
            <span class="text-[10px] opacity-75">({{ (pt * 100).toFixed(1) }}%)</span>
            <span 
              v-if="pt === safeInner" 
              class="text-[9px] px-1 rounded bg-neutral-100 text-neutral-600 font-sans"
              :class="{ 'bg-neutral-800 text-neutral-300': hoveredPointIndex === idx }"
            >
              {{ t('inner_deadzone') }}
            </span>
            <span 
              v-if="pt === safeOuter" 
              class="text-[9px] px-1 rounded bg-neutral-100 text-neutral-600 font-sans"
              :class="{ 'bg-neutral-800 text-neutral-300': hoveredPointIndex === idx }"
            >
              {{ t('outer_deadzone') }}
            </span>
          </div>
        </div>
      </div>
      <p class="text-[11px] text-neutral-400">
        {{ t('hover_highlight_tip') }}
      </p>
    </div>
  </div>
</template>
