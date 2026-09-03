<script setup lang="ts">
import { ref, reactive } from 'vue'
import type { RoiRect } from '../types/api'

const props = defineProps<{
  imageUrl: string | null
  imageWidth: number
  imageHeight: number
  currentRoi: RoiRect | null
}>()

const emit = defineEmits<{
  (e: 'update:roi', roi: RoiRect): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const isDragging = ref(false)
const dragStart = reactive({ x: 0, y: 0 })
const tempRoi = ref<RoiRect | null>(null)

function getImgCoords(clientX: number, clientY: number): { x: number; y: number } | null {
  if (!containerRef.value || !props.imageWidth || !props.imageHeight) return null
  const rect = containerRef.value.getBoundingClientRect()
  const relX = clientX - rect.left
  const relY = clientY - rect.top

  const scaleX = props.imageWidth / rect.width
  const scaleY = props.imageHeight / rect.height

  const imgX = Math.max(0, Math.min(props.imageWidth, relX * scaleX))
  const imgY = Math.max(0, Math.min(props.imageHeight, relY * scaleY))

  return { x: imgX, y: imgY }
}

function onMouseDown(e: MouseEvent) {
  if (!props.imageUrl) return
  const coords = getImgCoords(e.clientX, e.clientY)
  if (!coords) return

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

function onMouseMove(e: MouseEvent) {
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

function onMouseUp() {
  if (isDragging.value && tempRoi.value) {
    isDragging.value = false
    emit('update:roi', tempRoi.value)
    tempRoi.value = null
  }
}
</script>

<template>
  <div
    ref="containerRef"
    class="relative w-full overflow-hidden rounded-xl bg-black select-none cursor-crosshair border border-slate-800 flex items-center justify-center min-h-[300px]"
    @mousedown="onMouseDown"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @mouseleave="onMouseUp"
  >
    <!-- Background Preview Image -->
    <img
      v-if="imageUrl"
      :src="imageUrl"
      alt="Preview"
      class="w-full h-full object-contain pointer-events-none"
    />
    <div v-else class="text-slate-500 text-sm flex flex-col items-center">
      <p>暂无画面信号</p>
      <p class="text-xs text-slate-600 mt-1">请先选择游戏窗口并启动捕获</p>
    </div>

    <!-- Active/Temp ROI Overlay Box -->
    <div
      v-if="(tempRoi || currentRoi) && imageWidth && imageHeight"
      class="absolute border-2 border-indigo-400 bg-indigo-500/20 shadow-lg shadow-indigo-500/30 pointer-events-none transition-all duration-75"
      :style="{
        left: `${(((tempRoi || currentRoi)!.x) / imageWidth) * 100}%`,
        top: `${(((tempRoi || currentRoi)!.y) / imageHeight) * 100}%`,
        width: `${(((tempRoi || currentRoi)!.width) / imageWidth) * 100}%`,
        height: `${(((tempRoi || currentRoi)!.height) / imageHeight) * 100}%`,
      }"
    >
      <div class="absolute -top-6 left-0 bg-indigo-600 text-white text-[10px] font-mono px-1.5 py-0.5 rounded shadow">
        ROI: {{ (tempRoi || currentRoi)!.width }}×{{ (tempRoi || currentRoi)!.height }}
      </div>
      <!-- Corner Markers -->
      <div class="absolute -top-1 -left-1 w-2 h-2 bg-indigo-300 rounded-full"></div>
      <div class="absolute -top-1 -right-1 w-2 h-2 bg-indigo-300 rounded-full"></div>
      <div class="absolute -bottom-1 -left-1 w-2 h-2 bg-indigo-300 rounded-full"></div>
      <div class="absolute -bottom-1 -right-1 w-2 h-2 bg-indigo-300 rounded-full"></div>
    </div>
  </div>
</template>
