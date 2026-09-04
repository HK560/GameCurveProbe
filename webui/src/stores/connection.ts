import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../services/api'
import { ws } from '../services/ws'
import { t } from '../services/i18n'

export const useConnectionStore = defineStore('connection', () => {
  const token = ref<string>(api.getToken())
  const connected = ref<boolean>(false)
  const controllerReady = ref<boolean>(true)
  const controllerEnabled = ref<boolean>(true)
  const isUpdatingController = ref<boolean>(false)
  const error = ref<string | null>(null)

  async function checkHealth() {
    try {
      const res = await api.getHealth()
      connected.value = res.status === 'ok'
      controllerReady.value = res.controller_ready
      controllerEnabled.value = res.controller_enabled
      error.value = null
      return true
    } catch (err: any) {
      connected.value = false
      error.value = err.message || t('err_connect_failed')
      return false
    }
  }

  async function setControllerEnabled(enabled: boolean) {
    isUpdatingController.value = true
    try {
      const res = await api.setControllerEnabled(enabled)
      controllerEnabled.value = res.enabled
      controllerReady.value = res.available
    } finally {
      isUpdatingController.value = false
    }
  }

  function updateToken(newToken: string) {
    token.value = newToken
    api.setToken(newToken)
    ws.connectEvents()
    ws.connectPreview()
  }

  return {
    token,
    connected,
    controllerReady,
    controllerEnabled,
    isUpdatingController,
    error,
    checkHealth,
    setControllerEnabled,
    updateToken,
  }
})
