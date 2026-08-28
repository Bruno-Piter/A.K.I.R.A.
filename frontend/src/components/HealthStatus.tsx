import { useEffect, useState } from 'react'
import { apiStatus, getHealth, subscribeApiStatus } from '../api/client.ts'
import type { ApiStatus } from '../api/types.ts'

const POLL_MS = 10_000

export default function HealthStatus() {
  const [status, setStatus] = useState<ApiStatus>(apiStatus())

  useEffect(() => {
    const unsubscribe = subscribeApiStatus(setStatus)
    void getHealth()
    const timer = window.setInterval(() => {
      void getHealth()
    }, POLL_MS)
    return () => {
      unsubscribe()
      window.clearInterval(timer)
    }
  }, [])

  const online = status.online
  const health = status.health
  const label = online
    ? `online · v${health?.version ?? '—'} · ${health?.llm_provider ?? 'llm'}`
    : 'API offline, usando mocks'

  return (
    <span
      className={`health-pill ${online ? 'health-pill--online' : 'health-pill--offline'}`}
      title={status.lastError ?? status.message}
    >
      <span className="health-pill__dot" aria-hidden="true" />
      {label}
    </span>
  )
}