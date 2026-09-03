import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSessionStore } from '../src/stores/session'

describe('SessionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('handles ws sync event', () => {
    const store = useSessionStore()
    store.handleWsEvent({
      type: 'session_sync',
      payload: {
        session: {
          id: 'test-session-1',
          config: {
            capture_fps: 120,
            point_count: 17,
            repeats: 3,
            settle_ms: 120,
            sample_ms: 700,
            range_mode: 'full',
            inner_deadzone: 0.0,
            outer_deadzone: 1.0,
          },
        },
      },
    })
    expect(store.session?.id).toBe('test-session-1')
    expect(store.config?.point_count).toBe(17)
  })

  it('tracks active job and progress updates', () => {
    const store = useSessionStore()
    store.handleWsEvent({
      type: 'job_status',
      payload: {
        job: {
          id: 'job-123',
          kind: 'measurement',
          state: 'running',
        },
      },
    })
    expect(store.activeJob?.id).toBe('job-123')
    expect(store.activeJob?.state).toBe('running')

    store.handleWsEvent({
      type: 'job_progress',
      payload: {
        data: {
          current_point: 5,
          total_points: 17,
        },
      },
    })
    expect(store.activeJob?.progress?.current_point).toBe(5)
  })
})
