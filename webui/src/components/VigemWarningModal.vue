<script setup lang="ts">
import { ref, watch } from 'vue'
import { AlertTriangle, ExternalLink } from 'lucide-vue-next'
import { t } from '../services/i18n'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ close: [neverRemind: boolean] }>()
const neverRemind = ref(false)

watch(() => props.show, show => {
  if (show) neverRemind.value = false
})
</script>

<template>
  <div v-if="show" class="fixed inset-0 z-[120] flex items-center justify-center bg-black/45 p-4">
    <div role="dialog" aria-modal="true" aria-labelledby="vigem-warning-title" class="w-full max-w-md rounded-xl border border-neutral-200 bg-white p-6 shadow-xl">
      <div class="flex items-start gap-3">
        <div class="rounded-lg bg-amber-100 p-2 text-amber-700"><AlertTriangle class="h-5 w-5" /></div>
        <div class="space-y-2">
          <h2 id="vigem-warning-title" class="text-base font-semibold text-neutral-900">{{ t('vigem_warning_title') }}</h2>
          <p class="text-sm leading-relaxed text-neutral-600">{{ t('vigem_warning_desc') }}</p>
        </div>
      </div>
      <a href="https://github.com/nefarius/ViGEmBus/releases" target="_blank" rel="noopener noreferrer" class="mt-5 inline-flex items-center gap-2 text-sm font-medium text-neutral-900 underline underline-offset-4">
        {{ t('vigem_download') }} <ExternalLink class="h-4 w-4" />
      </a>
      <label class="mt-5 flex cursor-pointer items-center gap-2 text-sm text-neutral-600">
        <input v-model="neverRemind" type="checkbox" class="h-4 w-4 rounded border-neutral-300" />
        <span>{{ t('vigem_never_remind') }}</span>
      </label>
      <div class="mt-6 flex justify-end">
        <button type="button" class="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800" @click="emit('close', neverRemind)">{{ t('vigem_continue') }}</button>
      </div>
    </div>
  </div>
</template>
