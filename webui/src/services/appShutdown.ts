export function initiateApplicationShutdown(
  requestShutdown: () => Promise<unknown>,
  closeConnections: () => void,
  closeWindow: () => void,
): void {
  void requestShutdown().catch((error) => {
    console.debug('Application shutdown request ended while the service was exiting:', error)
  })
  closeConnections()
  globalThis.setTimeout(closeWindow, 150)
}
