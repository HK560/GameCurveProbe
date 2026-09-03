<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import { useSessionStore } from '../stores/session'
import { createProbeLease } from '../services/probeLease'
import { 
  Target, 
  Play, 
  Square, 
  Minus, 
  Plus, 
  ArrowLeft, 
  ArrowRight, 
  Activity, 
  CheckCircle2, 
  Sliders
} from 'lucide-vue-next'

const sessionStore = useSessionStore()

const currentOutput = ref<number>(0.05)
const currentStep = ref<number>(0.005)
const isMeasuringNoise = ref<boolean>(false)
const noiseSuccess = ref<boolean>(false)

const probeActive = computed(() => sessionStore.probe?.active ?? false)
const expiresCountdown = computed(() => sessionStore.probe?.expires_in ?? 0)

const config = computed(() => sessionStore.config)
const innerDeadzone = computed(() => config.value?.inner_deadzone ?? 0.0)
const outerDeadzone = computed(() => config.value?.outer_deadzone ?? 1.0)
const probeLease = createProbeLease(
  () => sessionStore.updateDeadzoneProbe(currentOutput.value),
  () => sessionStore.stopDeadzoneProbe(),
)

async function toggleProbe() {
  if (probeActive.value) {
    probeLease.pause()
    await sessionStore.stopDeadzoneProbe()
  } else {
    await sessionStore.startDeadzoneProbe(currentOutput.value, currentStep.value)
    probeLease.start()
  }
}

onBeforeUnmount(() => {
  if (probeActive.value) {
    void probeLease.dispose()
  } else {
    probeLease.pause()
  }
})

async function adjustOutput(delta: number) {
  const next = Math.max(0.0, Math.min(1.0, Math.round((currentOutput.value + delta) * 1000) / 1000))
  currentOutput.value = next
  if (probeActive.value) {
    await sessionStore.updateDeadzoneProbe(next)
  }
}

async function onSliderChange(e: Event) {
  const target = e.target as HTMLInputElement
  const val = parseFloat(target.value)
  currentOutput.value = val
  if (probeActive.value) {
    await sessionStore.updateDeadzoneProbe(val)
  }
}

async function setAsInnerDeadzone() {
  await sessionStore.updateConfig({ inner_deadzone: currentOutput.value })
}

async function setAsOuterDeadzone() {
  await sessionStore.updateConfig({ outer_deadzone: currentOutput.value })
}

async function runNoiseBenchmark() {
  isMeasuringNoise.value = true
  noiseSuccess.value = false
  try {
    await sessionStore.startIdleNoise()
    noiseSuccess.value = true
  } catch (err) {
    console.error('Failed to run noise test:', err)
  } finally {
    isMeasuringNoise.value = false
  }
}

function goBack() {
  sessionStore.activeStep = 1
}

function proceedToMeasurement() {
  sessionStore.activeStep = 3
}
</script>

<template>
  <div class="space-y-6">
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <!-- Left Column: Interactive Probing Tool -->
      <div class="lg:col-span-7 space-y-4">
        <div class="p-5 bg-white border border-neutral-200/80 rounded-xl space-y-5 shadow-xs">
          <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
            <div class="flex items-center space-x-2.5">
              <div class="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-900 flex items-center justify-center">
                <Target class="w-4 h-4" />
              </div>
              <div>
                <h3 class="text-xs font-semibold uppercase tracking-wider text-neutral-700">摇杆输出微调探测器</h3>
                <p class="text-[11px] text-neutral-400">实时输出右摇杆模拟信号，观察游戏视口微动以测定死区边界</p>
              </div>
            </div>

            <div v-if="probeActive" class="flex items-center space-x-2 px-2.5 py-0.5 bg-neutral-900 text-white rounded-full text-[11px] font-mono">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>输出生效中 ({{ expiresCountdown }}s)</span>
            </div>
          </div>

          <!-- Step Size Buttons -->
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-neutral-600">探测步长 (分辨率)</label>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="step in [0.001, 0.005, 0.01]"
                :key="step"
                @click="currentStep = step"
                class="py-1.5 px-3 rounded-lg text-xs font-mono font-medium transition cursor-pointer"
                :class="[
                  currentStep === step
                    ? 'bg-neutral-900 text-white'
                    : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200 hover:text-neutral-900'
                ]"
              >
                {{ step === 0.001 ? '0.001 (精细)' : step === 0.005 ? '0.005 (标准)' : '0.01 (快速)' }}
              </button>
            </div>
          </div>

          <!-- Output Value Display and Slider -->
          <div class="space-y-2 pt-1">
            <div class="flex items-center justify-between">
              <span class="text-xs font-medium text-neutral-600">当前右摇杆输出 (X+)</span>
              <span class="text-2xl font-bold font-mono text-neutral-900">
                {{ (currentOutput * 100).toFixed(1) }}%
                <span class="text-xs text-neutral-400 font-normal">({{ currentOutput.toFixed(3) }})</span>
              </span>
            </div>

            <input
              type="range"
              min="0.0"
              max="1.0"
              :step="currentStep"
              :value="currentOutput"
              @input="onSliderChange"
              class="w-full h-1.5 bg-neutral-200 rounded-lg appearance-none cursor-pointer accent-neutral-900"
            />

            <!-- Increment / Decrement Buttons -->
            <div class="flex items-center space-x-2 pt-1">
              <button
                @click="adjustOutput(-currentStep)"
                class="flex-1 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 py-1.5 rounded-lg text-xs font-medium flex items-center justify-center space-x-1 cursor-pointer transition"
              >
                <Minus class="w-3.5 h-3.5" />
                <span>-{{ currentStep }}</span>
              </button>
              <button
                @click="adjustOutput(currentStep)"
                class="flex-1 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 py-1.5 rounded-lg text-xs font-medium flex items-center justify-center space-x-1 cursor-pointer transition"
              >
                <Plus class="w-3.5 h-3.5" />
                <span>+{{ currentStep }}</span>
              </button>
            </div>
          </div>

          <!-- Probe Control & Set Deadzone Buttons -->
          <div class="space-y-2 pt-2 border-t border-neutral-100">
            <button
              @click="toggleProbe"
              class="w-full py-2.5 rounded-lg font-medium text-xs flex items-center justify-center space-x-2 transition cursor-pointer"
              :class="[
                probeActive
                  ? 'bg-rose-600 hover:bg-rose-700 text-white'
                  : 'bg-neutral-900 hover:bg-neutral-800 text-white'
              ]"
            >
              <Square v-if="probeActive" class="w-3.5 h-3.5 fill-current" />
              <Play v-else class="w-3.5 h-3.5 fill-current" />
              <span>{{ probeActive ? '释放摇杆 (停止测试)' : '激活摇杆实时输出' }}</span>
            </button>

            <div class="grid grid-cols-2 gap-2 pt-1">
              <button
                @click="setAsInnerDeadzone"
                class="bg-neutral-100 hover:bg-neutral-200 border border-neutral-200 text-neutral-800 py-2 px-3 rounded-lg text-xs font-medium transition cursor-pointer flex items-center justify-center space-x-1"
              >
                <CheckCircle2 class="w-3.5 h-3.5 text-neutral-600" />
                <span>设为内死区 ({{ currentOutput.toFixed(3) }})</span>
              </button>
              <button
                @click="setAsOuterDeadzone"
                class="bg-neutral-100 hover:bg-neutral-200 border border-neutral-200 text-neutral-800 py-2 px-3 rounded-lg text-xs font-medium transition cursor-pointer flex items-center justify-center space-x-1"
              >
                <CheckCircle2 class="w-3.5 h-3.5 text-neutral-600" />
                <span>设为外死区 ({{ currentOutput.toFixed(3) }})</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Deadzone Configuration Summary & Idle Noise Benchmark -->
      <div class="lg:col-span-5 space-y-4 flex flex-col justify-between">
        <div class="space-y-4">
          <!-- Configured Deadzones Card -->
          <div class="p-4 bg-white border border-neutral-200/80 rounded-xl space-y-3 shadow-xs">
            <div class="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
              <Sliders class="w-3.5 h-3.5" />
              <span>已设死区参数</span>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div class="p-3 bg-neutral-50 border border-neutral-200/60 rounded-lg">
                <div class="text-[11px] text-neutral-500">内死区 (Inner)</div>
                <div class="text-xl font-bold font-mono text-neutral-900 mt-1">
                  {{ (innerDeadzone * 100).toFixed(1) }}%
                </div>
                <div class="text-[10px] text-neutral-400 mt-0.5">起始响应阈值</div>
              </div>

              <div class="p-3 bg-neutral-50 border border-neutral-200/60 rounded-lg">
                <div class="text-[11px] text-neutral-500">外死区 (Outer)</div>
                <div class="text-xl font-bold font-mono text-neutral-900 mt-1">
                  {{ (outerDeadzone * 100).toFixed(1) }}%
                </div>
                <div class="text-[10px] text-neutral-400 mt-0.5">满速饱和阈值</div>
              </div>
            </div>
          </div>

          <!-- Noise Floor Benchmark Card -->
          <div class="p-4 bg-white border border-neutral-200/80 rounded-xl space-y-3 shadow-xs">
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                <Activity class="w-3.5 h-3.5" />
                <span>画面静止噪底校准</span>
              </div>
              <button
                @click="runNoiseBenchmark"
                :disabled="isMeasuringNoise"
                class="text-xs bg-neutral-900 hover:bg-neutral-800 disabled:opacity-40 text-white px-2.5 py-1 rounded-md transition cursor-pointer"
              >
                {{ isMeasuringNoise ? '采样中...' : '测定噪底' }}
              </button>
            </div>
            <p class="text-xs text-neutral-500">
              采样 ROI 画面在手柄回中静止时的背景微晃与噪点，用于滤除环境噪底。
            </p>
            <div v-if="sessionStore.noise" class="p-2.5 bg-neutral-50 border border-neutral-200/60 rounded-lg text-xs font-mono text-neutral-700 flex justify-between">
              <span>X噪底: {{ sessionStore.noise.floor_x }} px/s</span>
              <span>Y噪底: {{ sessionStore.noise.floor_y }} px/s</span>
            </div>
          </div>
        </div>

        <!-- Navigation Buttons -->
        <div class="flex items-center space-x-3 pt-2">
          <button
            @click="goBack"
            class="flex-1 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 font-medium py-2.5 px-4 rounded-lg flex items-center justify-center space-x-2 transition cursor-pointer text-xs"
          >
            <ArrowLeft class="w-4 h-4" />
            <span>上一步</span>
          </button>
          <button
            @click="proceedToMeasurement"
            class="flex-1 bg-neutral-900 hover:bg-neutral-800 text-white font-medium py-2.5 px-4 rounded-lg flex items-center justify-center space-x-2 transition cursor-pointer text-xs"
          >
            <span>下一步：曲线测定</span>
            <ArrowRight class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
