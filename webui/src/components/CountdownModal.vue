<script setup lang="ts">
import { computed, watch } from 'vue'
import { useSessionStore } from '../stores/session'
import { Monitor, Square, CheckCircle2 } from 'lucide-vue-next'
import { soundSynth } from '../services/sound'

const sessionStore = useSessionStore()

const activeJob = computed(() => sessionStore.activeJob)
const progressData = computed(() => activeJob.value?.progress)

const isCountdownPhase = computed(() => {
  if (!activeJob.value || activeJob.value.kind !== 'measurement') return false
  return progressData.value?.phase === 'countdown' || (typeof progressData.value?.remaining_seconds === 'number' && progressData.value.remaining_seconds > 0)
})

const remainingSeconds = computed(() => {
  return progressData.value?.remaining_seconds ?? 5
})

const totalSeconds = computed(() => {
  return progressData.value?.total_seconds ?? 5
})

// Play tick audio on countdown
watch(remainingSeconds, (newSec) => {
  if (isCountdownPhase.value && newSec > 0 && sessionStore.config?.sound_enabled !== false) {
    soundSynth.playTestSound()
  }
})

async function cancelMeasurement() {
  if (activeJob.value?.id) {
    await sessionStore.cancelJob(activeJob.value.id)
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="isCountdownPhase"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md"
      >
        <div
          class="bg-white border border-neutral-200 rounded-2xl shadow-2xl max-w-md w-full p-6 text-center space-y-6 overflow-hidden relative"
        >
          <!-- Header Icon & Title -->
          <div class="space-y-2">
            <div class="w-14 h-14 rounded-2xl bg-neutral-900 text-white mx-auto flex items-center justify-center shadow-lg">
              <Monitor class="w-7 h-7 animate-pulse" />
            </div>
            <h2 class="text-lg font-bold text-neutral-900">
              请切回游戏画面！
            </h2>
            <p class="text-xs text-neutral-500 leading-relaxed px-2">
              测定任务已启动。请在倒计时结束前切换至游戏窗口并保持游戏为前台聚焦状态。
            </p>
          </div>

          <!-- Big Countdown Visualizer -->
          <div class="py-4 flex flex-col items-center justify-center">
            <div class="relative w-28 h-28 flex items-center justify-center">
              <!-- Outer Ring -->
              <div class="absolute inset-0 rounded-full border-4 border-neutral-100"></div>
              <div
                class="absolute inset-0 rounded-full border-4 border-neutral-900 border-t-transparent animate-spin"
                style="animation-duration: 2s;"
              ></div>
              <!-- Number -->
              <span class="text-5xl font-extrabold font-mono text-neutral-900 tracking-tight">
                {{ remainingSeconds }}
              </span>
            </div>
            <span class="text-[11px] font-mono text-neutral-400 mt-3 font-medium">
              倒计时 {{ remainingSeconds }} / {{ totalSeconds }}s
            </span>
          </div>

          <!-- Action Buttons -->
          <div class="flex items-center space-x-3 pt-2">
            <button
              type="button"
              @click="cancelMeasurement"
              class="flex-1 py-2.5 px-4 rounded-xl border border-neutral-200 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 text-xs font-semibold flex items-center justify-center space-x-2 transition cursor-pointer"
            >
              <Square class="w-3.5 h-3.5 fill-current text-rose-600" />
              <span>放弃/中止</span>
            </button>
            <div
              class="flex-1 py-2.5 px-4 rounded-xl bg-neutral-900 text-white text-xs font-semibold flex items-center justify-center space-x-2 shadow-sm"
            >
              <CheckCircle2 class="w-3.5 h-3.5 text-emerald-400" />
              <span>请切回游戏</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
