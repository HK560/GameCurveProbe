import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../services/api'
import { ws } from '../services/ws'

export const useConnectionStore = defineStore('connection', () => {
  const token = ref<string>(api.getToken())
  const connected = ref<boolean>(false)
  const controllerReady = ref<boolean>(true)
  const error = ref<string | null>(null)

  async function checkHealth() {
    try {
      const res = await api.getHealth()
      connected.value = res.status === 'ok'
      controllerReady.value = res.controller_ready
      error.value = null
    } catch (err: any) {
      connected.value = false
      error.value = err.message || '无法连接到本地服务'
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
    error,
    checkHealth,
    updateToken,
  }
})
