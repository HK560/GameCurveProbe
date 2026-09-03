class SoundSynthesizer {
  private ctx: AudioContext | null = null

  private getContext(): AudioContext | null {
    if (typeof window === 'undefined') return null
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
      if (AudioCtx) {
        this.ctx = new AudioCtx()
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume()
    }
    return this.ctx
  }

  public playTone(freq: number, durationMs: number, type: OscillatorType = 'sine', gainVal = 0.15) {
    try {
      const ctx = this.getContext()
      if (!ctx) return

      const osc = ctx.createOscillator()
      const gain = ctx.createGain()

      osc.type = type
      osc.frequency.setValueAtTime(freq, ctx.currentTime)

      gain.gain.setValueAtTime(gainVal, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + durationMs / 1000)

      osc.connect(gain)
      gain.connect(ctx.destination)

      osc.start()
      osc.stop(ctx.currentTime + durationMs / 1000)
    } catch (err) {
      console.warn('Web Audio synthesis error:', err)
    }
  }

  public playStartSound() {
    this.playTone(523.25, 100, 'sine', 0.15) // C5
    setTimeout(() => {
      this.playTone(783.99, 150, 'sine', 0.15) // G5
    }, 100)
  }

  public playStopSound() {
    this.playTone(659.25, 100, 'triangle', 0.15) // E5
    setTimeout(() => {
      this.playTone(440.0, 150, 'triangle', 0.15) // A4
    }, 100)
  }

  public playCompleteSound() {
    this.playTone(523.25, 80, 'sine', 0.15) // C5
    setTimeout(() => {
      this.playTone(659.25, 80, 'sine', 0.15) // E5
    }, 80)
    setTimeout(() => {
      this.playTone(1046.5, 200, 'sine', 0.2) // C6
    }, 160)
  }

  public playTestSound() {
    this.playTone(783.99, 100, 'sine', 0.15)
    setTimeout(() => {
      this.playTone(1046.5, 150, 'sine', 0.2)
    }, 100)
  }
}

export const soundSynth = new SoundSynthesizer()
