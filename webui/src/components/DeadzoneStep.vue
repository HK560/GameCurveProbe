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
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Left Column: Interactive Probing Tool -->
      <div class="lg:col-span-7 space-y-4">
        <div class="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-5">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <div class="flex items-center space-x-2.5">
              <div class="w-8 h-8 rounded-lg bg-indigo-600/20 text-indigo-400 flex items-center justify-center">
                <Target class="w-5 h-5" />
              </div>
              <div>
                <h3 class="text-sm font-semibold text-white">摇杆输出微调探测器</h3>
                <p class="text-xs text-slate-400">实时输出右摇杆模拟信号，观察游戏视口微动以测定死区边界</p>
              </div>
            </div>

            <div v-if="probeActive" class="flex items-center space-x-2 px-3 py-1 bg-amber-500/10 border border-amber-500/40 rounded-full text-xs text-amber-300">
              <span class="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
              <span>输出生效中 (安全保护: {{ expiresCountdown }}s)</span>
            </div>
          </div>

          <!-- Step Size Buttons -->
          <div class="space-y-2">
            <label class="text-xs font-semibold text-slate-300">探测步长 (分辨率)</label>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="step in [0.001, 0.005, 0.01]"
                :key="step"
                @click="currentStep = step"
                class="py-1.5 px-3 rounded-lg border text-xs font-mono font-medium transition cursor-pointer"
                :class="[
                  currentStep === step
                    ? 'bg-indigo-600 border-indigo-500 text-white shadow-sm shadow-indigo-500/20'
                    : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
                ]"
              >
                {{ step === 0.001 ? '0.001 (精细)' : step === 0.005 ? '0.005 (标准)' : '0.01 (快速)' }}
              </button>
            </div>
          </div>

          <!-- Output Value Display and Slider -->
          <div class="space-y-3 pt-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-300">当前右摇杆输出 (X+)</span>
              <span class="text-2xl font-bold font-mono text-indigo-400">
                {{ (currentOutput * 100).toFixed(1) }}%
                <span class="text-xs text-slate-500 font-normal">({{ currentOutput.toFixed(3) }})</span>
              </span>
            </div>

            <input
              type="range"
              min="0.0"
              max="1.0"
              :step="currentStep"
              :value="currentOutput"
              @input="onSliderChange"
              class="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />

            <!-- Increment / Decrement Buttons -->
            <div class="flex items-center space-x-2 pt-1">
              <button
                @click="adjustOutput(-currentStep)"
                class="flex-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 py-2 rounded-lg text-sm flex items-center justify-center space-x-1 cursor-pointer"
              >
                <Minus class="w-4 h-4" />
                <span>-{{ currentStep }}</span>
              </button>
              <button
                @click="adjustOutput(currentStep)"
                class="flex-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 py-2 rounded-lg text-sm flex items-center justify-center space-x-1 cursor-pointer"
              >
                <Plus class="w-4 h-4" />
                <span>+{{ currentStep }}</span>
              </button>
            </div>
          </div>

          <!-- Probe Control & Set Deadzone Buttons -->
          <div class="space-y-2 pt-2 border-t border-slate-800">
            <button
              @click="toggleProbe"
              class="w-full py-2.5 rounded-xl font-semibold text-sm flex items-center justify-center space-x-2 transition cursor-pointer"
              :class="[
                probeActive
                  ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/30'
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30'
              ]"
            >
              <Square v-if="probeActive" class="w-4 h-4 fill-current" />
              <Play v-else class="w-4 h-4 fill-current" />
              <span>{{ probeActive ? '释放摇杆 (停止测试)' : '激活摇杆实时输出' }}</span>
            </button>

            <div class="grid grid-cols-2 gap-2 pt-1">
              <button
                @click="setAsInnerDeadzone"
                class="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-indigo-300 hover:text-indigo-200 py-2 px-3 rounded-lg text-xs font-medium transition cursor-pointer flex items-center justify-center space-x-1"
              >
                <CheckCircle2 class="w-3.5 h-3.5" />
                <span>设为内死区 ({{ currentOutput.toFixed(3) }})</span>
              </button>
              <button
                @click="setAsOuterDeadzone"
                class="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-purple-300 hover:text-purple-200 py-2 px-3 rounded-lg text-xs font-medium transition cursor-pointer flex items-center justify-center space-x-1"
              >
                <CheckCircle2 class="w-3.5 h-3.5" />
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
          <div class="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3">
            <div class="flex items-center space-x-2 text-sm font-semibold text-slate-200">
              <Sliders class="w-4 h-4 text-indigo-400" />
              <span>已设死区参数</span>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div class="p-3 bg-slate-800/60 border border-slate-700/60 rounded-lg">
                <div class="text-[11px] text-slate-400">内死区 (Inner Deadzone)</div>
                <div class="text-xl font-bold font-mono text-emerald-400 mt-1">
                  {{ (innerDeadzone * 100).toFixed(1) }}%
                </div>
                <div class="text-[10px] text-slate-500 mt-0.5">起始响应阈值</div>
              </div>

              <div class="p-3 bg-slate-800/60 border border-slate-700/60 rounded-lg">
                <div class="text-[11px] text-slate-400">外死区 (Outer Deadzone)</div>
                <div class="text-xl font-bold font-mono text-purple-400 mt-1">
                  {{ (outerDeadzone * 100).toFixed(1) }}%
                </div>
                <div class="text-[10px] text-slate-500 mt-0.5">满速饱和阈值</div>
              </div>
            </div>
          </div>

          <!-- Noise Floor Benchmark Card -->
          <div class="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-2 text-sm font-semibold text-slate-200">
                <Activity class="w-4 h-4 text-cyan-400" />
                <span>画面静止噪底校准</span>
              </div>
              <button
                @click="runNoiseBenchmark"
                :disabled="isMeasuringNoise"
                class="text-xs bg-slate-800 hover:bg-slate-700 text-cyan-300 px-2.5 py-1 rounded-lg border border-slate-700 transition cursor-pointer"
              >
                {{ isMeasuringNoise ? '采样中...' : '测定噪底' }}
              </button>
            </div>
            <p class="text-xs text-slate-400">
              采样 ROI 画面在手柄回中静止时的背景微晃与噪点，用于滤除环境噪底。
            </p>
            <div v-if="sessionStore.noise" class="p-2.5 bg-slate-800/40 rounded-lg text-xs font-mono text-cyan-300 flex justify-between">
              <span>X噪底: {{ sessionStore.noise.floor_x }} px/s</span>
              <span>Y噪底: {{ sessionStore.noise.floor_y }} px/s</span>
            </div>
          </div>
        </div>

        <!-- Navigation Buttons -->
        <div class="flex items-center space-x-3 pt-4 border-t border-slate-800">
          <button
            @click="goBack"
            class="flex-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold py-2.5 px-4 rounded-xl flex items-center justify-center space-x-2 transition cursor-pointer"
          >
            <ArrowLeft class="w-4 h-4" />
            <span>上一步</span>
          </button>
          <button
            @click="proceedToMeasurement"
            class="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 px-4 rounded-xl shadow-lg shadow-indigo-600/30 flex items-center justify-center space-x-2 transition cursor-pointer"
          >
            <span>下一步：曲线测定</span>
            <ArrowRight class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
