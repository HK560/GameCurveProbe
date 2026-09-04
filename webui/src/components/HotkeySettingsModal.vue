<script setup lang="ts">
import { ref, watch } from 'vue'
import { useSessionStore } from '../stores/session'
import { useConnectionStore } from '../stores/connection'
import { api } from '../services/api'
import { soundSynth } from '../services/sound'
import { t } from '../services/i18n'
import { X, Keyboard, Volume2, VolumeX, Sparkles, Check, Gamepad2, Settings } from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const sessionStore = useSessionStore()
const connectionStore = useConnectionStore()

const hotkeyEnabled = ref(true)
const hotkeyStart = ref('F9')
const hotkeyStop = ref('F10')
const hotkeyDzInc = ref('F7')
const hotkeyDzDec = ref('F6')
const soundEnabled = ref(true)
const autoWake = ref(true)
const wakeInput = ref('right_stick')
const isSaving = ref(false)
const isTestingSound = ref(false)
const isWaking = ref(false)
const saveSuccess = ref(false)

const startKeyOptions = [
  { label: 'F9 (Default)', value: 'F9' },
  { label: 'F8', value: 'F8' },
  { label: 'F11', value: 'F11' },
  { label: 'F12', value: 'F12' },
  { label: 'Ctrl + Alt + S', value: 'Ctrl+Alt+S' },
  { label: 'Shift + F9', value: 'Shift+F9' },
  { label: 'NumPad 1', value: 'NUMPAD1' },
]

const stopKeyOptions = [
  { label: 'F10 (Default)', value: 'F10' },
  { label: 'F9', value: 'F9' },
  { label: 'F8', value: 'F8' },
  { label: 'Escape', value: 'Escape' },
  { label: 'Ctrl + Alt + X', value: 'Ctrl+Alt+X' },
  { label: 'Shift + F10', value: 'Shift+F10' },
  { label: 'NumPad 0', value: 'NUMPAD0' },
]

const dzIncOptions = [
  { label: 'F7 (Default)', value: 'F7' },
  { label: 'F8', value: 'F8' },
  { label: 'PageUp', value: 'PAGEUP' },
  { label: 'Shift + F7', value: 'Shift+F7' },
  { label: 'Ctrl + Alt + Up', value: 'Ctrl+Alt+S' },
]

const dzDecOptions = [
  { label: 'F6 (Default)', value: 'F6' },
  { label: 'F5', value: 'F5' },
  { label: 'PageDown', value: 'PAGEDOWN' },
  { label: 'Shift + F6', value: 'Shift+F6' },
]

watch(
  () => props.show,
  (newVal) => {
    if (newVal && sessionStore.config) {
      hotkeyEnabled.value = sessionStore.config.hotkey_enabled ?? true
      hotkeyStart.value = sessionStore.config.hotkey_start || 'F9'
      hotkeyStop.value = sessionStore.config.hotkey_stop || 'F10'
      hotkeyDzInc.value = sessionStore.config.hotkey_dz_inc || 'F7'
      hotkeyDzDec.value = sessionStore.config.hotkey_dz_dec || 'F6'
      soundEnabled.value = sessionStore.config.sound_enabled ?? true
      autoWake.value = sessionStore.config.auto_wake ?? true
      wakeInput.value = sessionStore.config.wake_input || 'right_stick'
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
      hotkey_dz_inc: hotkeyDzInc.value,
      hotkey_dz_dec: hotkeyDzDec.value,
      sound_enabled: soundEnabled.value,
      auto_wake: autoWake.value,
      wake_input: wakeInput.value,
    })
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
      emit('close')
    }, 600)
  } catch (err: any) {
    console.error('Failed to save hotkey settings:', err)
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

async function testWakeGame() {
  isWaking.value = true
  try {
    await api.wakeController(wakeInput.value)
    setTimeout(() => { isWaking.value = false }, 500)
  } catch (err: any) {
    isWaking.value = false
    window.alert(err.message || t('wake_failed'))
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
            <Settings class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-sm font-semibold text-neutral-900">{{ t('settings') }}</h3>
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
              <span class="font-medium text-neutral-900">{{ t('win_hotkeys_title') }}</span>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="hotkeyEnabled" class="sr-only peer" />
              <div class="w-9 h-5 bg-neutral-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-neutral-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-neutral-900"></div>
            </label>
          </div>
          <p class="text-[11px] text-neutral-500 leading-relaxed">
            {{ t('win_hotkeys_desc') }}
          </p>

          <div v-if="hotkeyEnabled" class="grid grid-cols-2 gap-3 pt-1">
            <div class="space-y-1">
              <label class="text-[11px] font-medium text-neutral-600">{{ t('hotkey_start_label') }}</label>
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
              <label class="text-[11px] font-medium text-neutral-600">{{ t('hotkey_stop_label') }}</label>
              <select
                v-model="hotkeyStop"
                class="w-full bg-white border border-neutral-200 rounded-lg px-2.5 py-1.5 text-xs font-mono text-neutral-900 focus:outline-none focus:border-neutral-900"
              >
                <option v-for="opt in stopKeyOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>

            <div class="space-y-1">
              <label class="text-[11px] font-medium text-neutral-600">{{ t('hotkey_dz_inc_label') }}</label>
              <select
                v-model="hotkeyDzInc"
                class="w-full bg-white border border-neutral-200 rounded-lg px-2.5 py-1.5 text-xs font-mono text-neutral-900 focus:outline-none focus:border-neutral-900"
              >
                <option v-for="opt in dzIncOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>

            <div class="space-y-1">
              <label class="text-[11px] font-medium text-neutral-600">{{ t('hotkey_dz_dec_label') }}</label>
              <select
                v-model="hotkeyDzDec"
                class="w-full bg-white border border-neutral-200 rounded-lg px-2.5 py-1.5 text-xs font-mono text-neutral-900 focus:outline-none focus:border-neutral-900"
              >
                <option v-for="opt in dzDecOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>
          </div>
        </div>

        <!-- Auto Wake Card -->
        <div class="space-y-3 p-3.5 bg-neutral-50 border border-neutral-200/70 rounded-xl">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <Gamepad2 class="w-4 h-4 text-neutral-800" />
              <span class="font-medium text-neutral-900">{{ t('auto_wake_game') }}</span>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="autoWake" class="sr-only peer" />
              <div class="w-9 h-5 bg-neutral-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-neutral-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-neutral-900"></div>
            </label>
          </div>
          <p class="text-[11px] text-neutral-500 leading-relaxed">
            {{ t('auto_wake_desc') }}
          </p>
          <div v-if="autoWake" class="space-y-1.5 pt-1">
            <div class="flex items-center justify-between">
              <label class="text-[11px] font-medium text-neutral-600">{{ t('wake_key') }}</label>
              <button
                type="button"
                :disabled="isWaking || !connectionStore.controllerEnabled"
                @click="testWakeGame"
                class="px-2 py-0.5 rounded-md bg-neutral-900 text-white hover:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed text-[11px] font-medium transition cursor-pointer"
                :title="t('press_wake_hint')"
              >
                {{ isWaking ? t('waking') : t('test_wake') }}
              </button>
            </div>
            <select
              v-model="wakeInput"
              class="w-full bg-white border border-neutral-200 rounded-lg px-2.5 py-1.5 text-xs font-mono text-neutral-900 focus:outline-none focus:border-neutral-900"
            >
              <optgroup :label="t('wake_group_basic')">
                <option value="right_stick">{{ t('wake_opt_right_stick') }}</option>
                <option value="left_stick">{{ t('wake_opt_left_stick') }}</option>
                <option value="a">{{ t('wake_opt_a') }}</option>
                <option value="b">{{ t('wake_opt_b') }}</option>
                <option value="x">{{ t('wake_opt_x') }}</option>
                <option value="y">{{ t('wake_opt_y') }}</option>
              </optgroup>
              <optgroup :label="t('wake_group_bumper_trigger')">
                <option value="left_bumper">{{ t('wake_opt_lb') }}</option>
                <option value="right_bumper">{{ t('wake_opt_rb') }}</option>
                <option value="left_trigger">{{ t('wake_opt_lt') }}</option>
                <option value="right_trigger">{{ t('wake_opt_rt') }}</option>
              </optgroup>
              <optgroup :label="t('wake_group_function')">
                <option value="start">{{ t('wake_opt_start') }}</option>
                <option value="back">{{ t('wake_opt_back') }}</option>
                <option value="guide">{{ t('wake_opt_guide') }}</option>
              </optgroup>
              <optgroup :label="t('wake_group_dpad')">
                <option value="dpad_up">{{ t('wake_opt_dpad_up') }}</option>
                <option value="dpad_down">{{ t('wake_opt_dpad_down') }}</option>
                <option value="dpad_left">{{ t('wake_opt_dpad_left') }}</option>
                <option value="dpad_right">{{ t('wake_opt_dpad_right') }}</option>
              </optgroup>
              <optgroup :label="t('wake_group_stick_pulse')">
                <option value="left_stick_up">{{ t('wake_opt_ls_up') }}</option>
                <option value="left_stick_down">{{ t('wake_opt_ls_down') }}</option>
                <option value="left_stick_left">{{ t('wake_opt_ls_left') }}</option>
                <option value="left_stick_right">{{ t('wake_opt_ls_right') }}</option>
                <option value="right_stick_up">{{ t('wake_opt_rs_up') }}</option>
                <option value="right_stick_down">{{ t('wake_opt_rs_down') }}</option>
                <option value="right_stick_left">{{ t('wake_opt_rs_left') }}</option>
                <option value="right_stick_right">{{ t('wake_opt_rs_right') }}</option>
              </optgroup>
            </select>
          </div>
        </div>

        <!-- Sound Effects Card -->
        <div class="space-y-3 p-3.5 bg-neutral-50 border border-neutral-200/70 rounded-xl">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <Volume2 v-if="soundEnabled" class="w-4 h-4 text-neutral-800" />
              <VolumeX v-else class="w-4 h-4 text-neutral-400" />
              <span class="font-medium text-neutral-900">{{ t('sound_effects') }}</span>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="soundEnabled" class="sr-only peer" />
              <div class="w-9 h-5 bg-neutral-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-neutral-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-neutral-900"></div>
            </label>
          </div>

          <p class="text-[11px] text-neutral-500 leading-relaxed">
            {{ t('sound_desc') }}
          </p>

          <div v-if="soundEnabled" class="flex items-center space-x-2 pt-1">
            <button
              @click="testSound('start')"
              :disabled="isTestingSound"
              class="flex-1 bg-white hover:bg-neutral-100 border border-neutral-200 text-neutral-700 py-1.5 px-2 rounded-lg text-[11px] flex items-center justify-center space-x-1 transition cursor-pointer"
            >
              <Sparkles class="w-3 h-3 text-emerald-600" />
              <span>{{ t('test_start_sound') }}</span>
            </button>

            <button
              @click="testSound('stop')"
              :disabled="isTestingSound"
              class="flex-1 bg-white hover:bg-neutral-100 border border-neutral-200 text-neutral-700 py-1.5 px-2 rounded-lg text-[11px] flex items-center justify-center space-x-1 transition cursor-pointer"
            >
              <Sparkles class="w-3 h-3 text-rose-600" />
              <span>{{ t('test_stop_sound') }}</span>
            </button>

            <button
              @click="testSound('complete')"
              :disabled="isTestingSound"
              class="flex-1 bg-white hover:bg-neutral-100 border border-neutral-200 text-neutral-700 py-1.5 px-2 rounded-lg text-[11px] flex items-center justify-center space-x-1 transition cursor-pointer"
            >
              <Sparkles class="w-3 h-3 text-sky-600" />
              <span>{{ t('test_complete_sound') }}</span>
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
          {{ t('cancel') }}
        </button>
        <button
          @click="saveSettings"
          :disabled="isSaving"
          class="px-4 py-1.5 bg-neutral-900 hover:bg-neutral-800 text-white rounded-lg text-xs font-medium flex items-center space-x-1.5 transition cursor-pointer disabled:opacity-50"
        >
          <Check v-if="saveSuccess" class="w-3.5 h-3.5 text-emerald-400" />
          <span>{{ isSaving ? t('saving') : saveSuccess ? t('saved') : t('save') }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
