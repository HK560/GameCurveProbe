<script setup lang="ts">
import { ref, watch } from 'vue'
import { useSessionStore } from '../stores/session'
import { api } from '../services/api'
import { soundSynth } from '../services/sound'
import { X, Keyboard, Volume2, VolumeX, Sparkles, Check } from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const sessionStore = useSessionStore()

const hotkeyEnabled = ref(true)
const hotkeyStart = ref('F9')
const hotkeyStop = ref('F10')
const soundEnabled = ref(true)
const isSaving = ref(false)
const isTestingSound = ref(false)
const saveSuccess = ref(false)

const startKeyOptions = [
  { label: 'F9 (默认)', value: 'F9' },
  { label: 'F8', value: 'F8' },
  { label: 'F11', value: 'F11' },
  { label: 'F12', value: 'F12' },
  { label: 'Ctrl + Alt + S', value: 'Ctrl+Alt+S' },
  { label: 'Shift + F9', value: 'Shift+F9' },
  { label: 'NumPad 1', value: 'NUMPAD1' },
]

const stopKeyOptions = [
  { label: 'F10 (默认)', value: 'F10' },
  { label: 'F9', value: 'F9' },
  { label: 'F8', value: 'F8' },
  { label: 'Escape', value: 'Escape' },
  { label: 'Ctrl + Alt + X', value: 'Ctrl+Alt+X' },
  { label: 'Shift + F10', value: 'Shift+F10' },
  { label: 'NumPad 0', value: 'NUMPAD0' },
]

watch(
  () => props.show,
  (newVal) => {
    if (newVal && sessionStore.config) {
      hotkeyEnabled.value = sessionStore.config.hotkey_enabled ?? true
      hotkeyStart.value = sessionStore.config.hotkey_start || 'F9'
      hotkeyStop.value = sessionStore.config.hotkey_stop || 'F10'
      soundEnabled.value = sessionStore.config.sound_enabled ?? true
    }
  },
  { immediate: true }
)

async function saveSettings() {
  isSaving.value = true
  saveSuccess.value = false
  try {
    await sessionStore.updateConfig({
      hotkey_enabled: hotkeyEnabled.value,
      hotkey_start: hotkeyStart.value,
      hotkey_stop: hotkeyStop.value,
      sound_enabled: soundEnabled.value,
    })
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
      emit('close')
    }, 600)
  } catch (err: any) {
    alert(err.message || '快捷键配置更新失败')
  } finally {
    isSaving.value = false
  }
}

async function testSound(type: 'start' | 'stop' | 'complete' | 'test') {
  isTestingSound.value = true
  try {
    soundSynth.playTone(784, 100, 'sine', 0.15)
    await api.testAudio(type)
  } catch (err) {
    console.warn('Audio test error:', err)
  } finally {
    setTimeout(() => { isTestingSound.value = false }, 300)
  }
}
</script>

<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center bg-neutral-900/50 backdrop-blur-xs p-4">
    <div class="bg-white rounded-2xl border border-neutral-200 shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
      <!-- Header -->
      <div class="px-5 py-4 border-b border-neutral-100 flex items-center justify-between bg-neutral-50/50">
        <div class="flex items-center space-x-2.5">
          <div class="w-8 h-8 rounded-lg bg-neutral-900 flex items-center justify-center text-white">
            <Keyboard class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-sm font-semibold text-neutral-900">快捷键与音效设置</h3>
            <p class="text-[11px] text-neutral-400">设置系统全局热键及操作音效提示</p>
          </div>
        </div>
        <button
          @click="emit('close')"
          class="p-1 rounded-lg text-neutral-400 hover:text-neutral-700 hover:bg-neutral-200/50 transition cursor-pointer"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Body -->
      <div class="p-5 space-y-5 text-xs text-neutral-700">
        <!-- Global Hotkeys Card -->
        <div class="space-y-3 p-3.5 bg-neutral-50 border border-neutral-200/70 rounded-xl">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <Keyboard class="w-4 h-4 text-neutral-800" />
              <span class="font-medium text-neutral-900">Windows 全局快捷键</span>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="hotkeyEnabled" class="sr-only peer" />
              <div class="w-9 h-5 bg-neutral-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-neutral-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-neutral-900"></div>
            </label>
          </div>
          <p class="text-[11px] text-neutral-500 leading-relaxed">
            启用后在游戏前台界面无需切出窗口，即可通过热键启动或中止测定。
          </p>

          <div v-if="hotkeyEnabled" class="grid grid-cols-2 gap-3 pt-1">
            <div class="space-y-1">
              <label class="text-[11px] font-medium text-neutral-600">开始测定快捷键</label>
              <select
                v-model="hotkeyStart"
                class="w-full bg-white border border-neutral-200 rounded-lg px-2.5 py-1.5 text-xs font-mono text-neutral-900 focus:outline-none focus:border-neutral-900"
              >
                <option v-for="opt in startKeyOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>

            <div class="space-y-1">
              <label class="text-[11px] font-medium text-neutral-600">停止测定快捷键</label>
              <select
                v-model="hotkeyStop"
                class="w-full bg-white border border-neutral-200 rounded-lg px-2.5 py-1.5 text-xs font-mono text-neutral-900 focus:outline-none focus:border-neutral-900"
              >
                <option v-for="opt in stopKeyOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>
          </div>
        </div>

        <!-- Sound Effects Card -->
        <div class="space-y-3 p-3.5 bg-neutral-50 border border-neutral-200/70 rounded-xl">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <Volume2 v-if="soundEnabled" class="w-4 h-4 text-neutral-800" />
              <VolumeX v-else class="w-4 h-4 text-neutral-400" />
              <span class="font-medium text-neutral-900">操作音效提示</span>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="soundEnabled" class="sr-only peer" />
              <div class="w-9 h-5 bg-neutral-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-neutral-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-neutral-900"></div>
            </label>
          </div>

          <p class="text-[11px] text-neutral-500 leading-relaxed">
            启动升调双音、中止降调双音与完成三连音提示，保障游戏盲操作的明确反馈。
          </p>

          <div v-if="soundEnabled" class="flex items-center space-x-2 pt-1">
            <button
              @click="testSound('start')"
              :disabled="isTestingSound"
              class="flex-1 bg-white hover:bg-neutral-100 border border-neutral-200 text-neutral-700 py-1.5 px-2 rounded-lg text-[11px] flex items-center justify-center space-x-1 transition cursor-pointer"
            >
              <Sparkles class="w-3 h-3 text-emerald-600" />
              <span>试听启动音</span>
            </button>

            <button
              @click="testSound('stop')"
              :disabled="isTestingSound"
              class="flex-1 bg-white hover:bg-neutral-100 border border-neutral-200 text-neutral-700 py-1.5 px-2 rounded-lg text-[11px] flex items-center justify-center space-x-1 transition cursor-pointer"
            >
              <Sparkles class="w-3 h-3 text-rose-600" />
              <span>试听中止音</span>
            </button>

            <button
              @click="testSound('complete')"
              :disabled="isTestingSound"
              class="flex-1 bg-white hover:bg-neutral-100 border border-neutral-200 text-neutral-700 py-1.5 px-2 rounded-lg text-[11px] flex items-center justify-center space-x-1 transition cursor-pointer"
            >
              <Sparkles class="w-3 h-3 text-sky-600" />
              <span>试听完成音</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-5 py-3.5 border-t border-neutral-100 bg-neutral-50/50 flex items-center justify-end space-x-3">
        <button
          @click="emit('close')"
          class="px-4 py-1.5 rounded-lg text-xs font-medium text-neutral-600 hover:bg-neutral-200/60 transition cursor-pointer"
        >
          取消
        </button>
        <button
          @click="saveSettings"
          :disabled="isSaving"
          class="px-4 py-1.5 bg-neutral-900 hover:bg-neutral-800 text-white rounded-lg text-xs font-medium flex items-center space-x-1.5 transition cursor-pointer disabled:opacity-50"
        >
          <Check v-if="saveSuccess" class="w-3.5 h-3.5 text-emerald-400" />
          <span>{{ isSaving ? '保存中…' : saveSuccess ? '已保存' : '保存设置' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
