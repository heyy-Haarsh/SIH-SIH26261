import { Badge } from '@/components/ui/Badge'
import type { IntegrationHealth } from '@/types'

const TONE: Record<IntegrationHealth, 'pass' | 'warning' | 'failed' | 'neutral' | 'info'> = {
  healthy: 'pass',
  degraded: 'warning',
  unavailable: 'failed',
  not_configured: 'neutral',
  disabled: 'neutral',
  simulated: 'info',
}

const LABEL: Record<IntegrationHealth, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  unavailable: 'Unavailable',
  not_configured: 'Not connected',
  disabled: 'Switched off',
  simulated: 'Simulated only',
}

export function healthLabel(health: IntegrationHealth): string {
  return LABEL[health] ?? health
}

export function HealthBadge({ health }: { health: IntegrationHealth }) {
  return <Badge tone={TONE[health] ?? 'neutral'}>{LABEL[health] ?? health}</Badge>
}

export function overallLabel(status: 'ok' | 'degraded' | 'unavailable'): {
  label: string
  tone: 'pass' | 'warning' | 'failed'
} {
  if (status === 'ok') return { label: 'All core services healthy', tone: 'pass' }
  if (status === 'degraded') return { label: 'Running with limitations', tone: 'warning' }
  return { label: 'A core service is down', tone: 'failed' }
}
