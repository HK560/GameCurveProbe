<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import type { RoiRect } from '../types/api'
import { t } from '../services/i18n'

const props = defineProps<{
  imageUrl: string | null
  imageWidth: number
  imageHeight: number
  currentRoi: RoiRect | null
}>()

const emit = defineEmits<{
  (e: 'update:roi', roi: RoiRect): void
}>()

const stageRef = ref<HTMLDivElement | null>(null)
const isDragging = ref(false)
const dragStart = reactive({ x: 0, y: 0 })
const tempRoi = ref<RoiRect | null>(null)

const activeRoi = computed(() => tempRoi.value || props.currentRoi)

const stageStyle = computed(() => {
  const w = props.imageWidth || 1920
  const h = props.imageHeight || 1080
  return {
    aspectRatio: `${w} / ${h}`,
    width: '100%',
  }
})

function getImgCoords(clientX: number, clientY: number): { x: number; y: number } | null {
  if (!stageRef.value || !props.imageWidth || !props.imageHeight) return null
  const rect = stageRef.value.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return null

  const relX = clientX - rect.left
  const relY = clientY - rect.top

  const scaleX = props.imageWidth / rect.width
  const scaleY = props.imageHeight / rect.height

  const imgX = Math.max(0, Math.min(props.imageWidth, relX * scaleX))
  const imgY = Math.max(0, Math.min(props.imageHeight, relY * scaleY))

  return { x: imgX, y: imgY }
}

function onPointerDown(e: PointerEvent) {
  if (!props.imageUrl || !stageRef.value) return
  const coords = getImgCoords(e.clientX, e.clientY)
  if (!coords) return

  const target = e.currentTarget as HTMLElement
  try {
    target.setPointerCapture(e.pointerId)
  } catch {
    // ignore
  }

  isDragging.value = true
  dragStart.x = coords.x
  dragStart.y = coords.y
  tempRoi.value = {
    x: Math.round(coords.x),
    y: Math.round(coords.y),
    width: 32,
    height: 32,
  }
}

function onPointerMove(e: PointerEvent) {
  if (!isDragging.value) return
  const coords = getImgCoords(e.clientX, e.clientY)
  if (!coords) return

  const left = Math.min(dragStart.x, coords.x)
  const top = Math.min(dragStart.y, coords.y)
  const width = Math.max(32, Math.abs(coords.x - dragStart.x))
  const height = Math.max(32, Math.abs(coords.y - dragStart.y))

  // Clamp inside image bounds
  const clampedX = Math.max(0, Math.min(left, props.imageWidth - 32))
  const clampedY = Math.max(0, Math.min(top, props.imageHeight - 32))
  const clampedW = Math.max(32, Math.min(width, props.imageWidth - clampedX))
  const clampedH = Math.max(32, Math.min(height, props.imageHeight - clampedY))

  tempRoi.value = {
    x: Math.round(clampedX),
    y: Math.round(clampedY),
    width: Math.round(clampedW),
    height: Math.round(clampedH),
  }
}

function onPointerUp(e: PointerEvent) {
  if (isDragging.value) {
    try {
      const target = e.currentTarget as HTMLElement
      if (target.hasPointerCapture(e.pointerId)) {
        target.releasePointerCapture(e.pointerId)
      }
    } catch {
      // ignore
    }
    isDragging.value = false
    if (tempRoi.value) {
      emit('update:roi', tempRoi.value)
      tempRoi.value = null
    }
  }
}
</script>

<template>
  <div
    class="relative w-full overflow-hidden rounded-xl bg-neutral-950 select-none border border-neutral-200/80 flex items-center justify-center min-h-[300px]"
  >
    <!-- Stage exactly matches the image aspect ratio to prevent letterbox coordinate desync -->
    <div
      ref="stageRef"
      class="relative cursor-crosshair select-none flex items-center justify-center max-w-full max-h-full"
      :style="stageStyle"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
    >
      <!-- Background Preview Image -->
      <img
        v-if="imageUrl"
        :src="imageUrl"
        alt="Preview"
        class="w-full h-full block object-contain pointer-events-none select-none"
      />
      <div v-else class="text-neutral-500 text-xs flex flex-col items-center py-16 px-4">
        <p>{{ t('no_signal_preview') }}</p>
        <p class="text-[11px] text-neutral-600 mt-1">{{ t('select_window_signal_hint') }}</p>
      </div>

      <!-- Active/Temp ROI Overlay Box (No transition delay, 1:1 follow cursor) -->
      <div
        v-if="activeRoi && imageWidth && imageHeight"
        class="absolute border-2 border-white bg-white/10 pointer-events-none transition-none shadow-sm"
        :style="{
          left: `${(activeRoi.x / imageWidth) * 100}%`,
          top: `${(activeRoi.y / imageHeight) * 100}%`,
          width: `${(activeRoi.width / imageWidth) * 100}%`,
          height: `${(activeRoi.height / imageHeight) * 100}%`,
        }"
      >
        <div class="absolute -top-6 left-0 bg-neutral-900 text-white text-[10px] font-mono px-1.5 py-0.5 rounded border border-neutral-700 shadow-sm whitespace-nowrap">
          ROI: {{ activeRoi.width }}×{{ activeRoi.height }}
        </div>
        <!-- Corner Markers -->
        <div class="absolute -top-1 -left-1 w-1.5 h-1.5 bg-white rounded-full"></div>
        <div class="absolute -top-1 -right-1 w-1.5 h-1.5 bg-white rounded-full"></div>
        <div class="absolute -bottom-1 -left-1 w-1.5 h-1.5 bg-white rounded-full"></div>
        <div class="absolute -bottom-1 -right-1 w-1.5 h-1.5 bg-white rounded-full"></div>
      </div>
    </div>
  </div>
</template>
