import { useState } from 'react'
import { RefreshCw, Shield, ShieldAlert, ShieldCheck, ShieldQuestion } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { api } from '@/services/api'
import type { ApplicationDetail, ForensicsIndicator, ForensicsRiskClass } from '@/types'
import { ResolveControl } from './ResolveControl'
import { errorText, type Resolution, type Tone } from './scrutinyUi'

const RISK_PLAIN: Record<
  ForensicsRiskClass,
  { label: string; meaning: string; tone: Tone; bar: string }
> = {
  informational: {
    label: 'For information',
    meaning: 'A neutral observation. No action is needed.',
    tone: 'info',
    bar: 'border-l-[#7f98b5]',
  },
  check_limitation: {
    label: 'A check could not be done',
    meaning:
      'The system could not run this check (for example no metadata, or the file is unsigned). That is a limit of the check, not a sign of tampering.',
    tone: 'neutral',
    bar: 'border-l-gray-400',
  },
  technical_anomaly: {
    label: 'Technical irregularity',
    meaning:
      'The file has an unusual technical property. Many genuine files do too; look at the original before drawing any conclusion.',
    tone: 'warning',
    bar: 'border-l-[#a98a4f]',
  },
  authenticity_concern: {
    label: 'Possible authenticity concern',
    meaning:
      'A stronger signal that the document may have been altered or is not what it claims. It is not proof. Examine the original and, if needed, ask the applicant to clarify.',
    tone: 'failed',
    bar: 'border-l-[#a8665f]',
  },
  possible_duplicate: {
    label: 'Possible duplicate',
    meaning:
      'This file matches or closely resembles another upload. It may be an honest re-upload.',
    tone: 'manual',
    bar: 'border-l-[#8478a3]',
  },
}

const SERIOUS: ForensicsRiskClass[] = ['technical_anomaly', 'authenticity_concern', 'possible_duplicate']

interface Props {
  detail: ApplicationDetail
  role: string
  onChanged: () => Promise<unknown> | void
}

export function AuthenticityPanel({ detail, role, onChanged }: Props) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const canAct = role === 'officer' || role === 'regional_officer'
  const indicators = detail.forensicsIndicators ?? []

  const byDoc = detail.documents.map((d) => ({
    doc: d,
    items: indicators.filter((i) => i.documentId === d.id),
  }))
  const appLevel = indicators.filter((i) => !i.documentId)

  async function run() {
    setBusy(true)
    setMsg(null)
    try {
      await api.runForensics(role, detail.id)
      setMsg('Authenticity checks re-run on the current files.')
      await onChanged()
    } catch (err) {
      setMsg(errorText(err, 'Authenticity checks failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Shield size={16} /> Authenticity &amp; forensics
          </h3>
          <p className="mt-1 text-xs text-ink-muted">
            These checks look for technical signs of editing, missing signatures and duplicate files.
            <strong className="text-ink"> A clean result does not prove a document is genuine</strong>
            , and a flag is not an accusation: it is a prompt to look at the original.
          </p>
        </div>
        {canAct && (
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            leftIcon={<RefreshCw size={14} />}
            onClick={() => void run()}
          >
            {busy ? 'Analysing…' : 'Re-run checks'}
          </Button>
        )}
      </div>

      {msg && (
        <div className="rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-xs text-ink-secondary">
          {msg}
        </div>
      )}

      {(detail.forensicsLimitations ?? []).length > 0 && (
        <div className="rounded-[var(--radius-md)] border border-[#e3d8bd] bg-status-warning-bg px-3 py-2 text-xs text-status-warning">
          <div className="mb-1 font-medium">What these checks could not do</div>
          <ul className="list-disc pl-4">
            {(detail.forensicsLimitations ?? []).map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </div>
      )}

      {byDoc.map(({ doc, items }) => (
        <section key={doc.id} className="rounded-[var(--radius-md)] border border-border">
          <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface px-3 py-2">
            <div className="flex items-center gap-2 text-sm font-medium text-ink">
              <StatusIcon items={items} />
              {doc.name}
              <span className="text-[11px] font-normal text-ink-muted">
                {doc.fileName} · v{doc.version}
              </span>
            </div>
            <Summary items={items} />
          </header>
          <div className="space-y-2 p-3">
            {items.length === 0 && (
              <p className="text-xs text-ink-muted">
                No open signals for this file. This means nothing unusual was detected by the local
                checks — not that the document has been verified with its issuer.
              </p>
            )}
            {items.map((ind) => (
              <IndicatorCard
                key={ind.id}
                ind={ind}
                canAct={canAct}
                role={role}
                onChanged={onChanged}
              />
            ))}
          </div>
        </section>
      ))}

      {appLevel.length > 0 && (
        <section className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Across documents
          </h4>
          {appLevel.map((ind) => (
            <IndicatorCard key={ind.id} ind={ind} canAct={canAct} role={role} onChanged={onChanged} />
          ))}
        </section>
      )}

      <section>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Verification with official sources (latest run)
        </h4>
        <ul className="space-y-2">
          {detail.verifications.map((v) => (
            <li
              key={v.id}
              className="flex flex-wrap items-start justify-between gap-2 rounded-[var(--radius-md)] border border-border px-3 py-2 text-xs"
            >
              <div className="min-w-0">
                <div className="font-medium text-ink">{v.claim}</div>
                <p className="text-ink-secondary">{v.detail}</p>
              </div>
              <Badge
                tone={
                  v.status === 'verified_by_source'
                    ? 'pass'
                    : v.status === 'mismatch_detected'
                      ? 'failed'
                      : 'neutral'
                }
              >
                {v.status.replace(/_/g, ' ')} · {v.source.replace(/_/g, ' ')}
              </Badge>
            </li>
          ))}
          {detail.verifications.length === 0 && (
            <li className="text-xs text-ink-muted">No verification has run yet.</li>
          )}
        </ul>
      </section>
    </div>
  )
}

function StatusIcon({ items }: { items: ForensicsIndicator[] }) {
  if (items.some((i) => i.riskClass === 'authenticity_concern'))
    return <ShieldAlert size={16} className="text-status-failed" />
  if (items.some((i) => SERIOUS.includes(i.riskClass)))
    return <ShieldQuestion size={16} className="text-status-warning" />
  return <ShieldCheck size={16} className="text-status-pass" />
}

function Summary({ items }: { items: ForensicsIndicator[] }) {
  const serious = items.filter((i) => SERIOUS.includes(i.riskClass)).length
  const limits = items.filter((i) => i.riskClass === 'check_limitation').length
  return (
    <div className="flex gap-1">
      {serious > 0 && <Badge tone="warning">{serious} to examine</Badge>}
      {limits > 0 && <Badge tone="neutral">{limits} check limitation(s)</Badge>}
      {serious === 0 && limits === 0 && <Badge tone="pass">nothing detected</Badge>}
    </div>
  )
}

function IndicatorCard({
  ind,
  canAct,
  role,
  onChanged,
}: {
  ind: ForensicsIndicator
  canAct: boolean
  role: string
  onChanged: () => Promise<unknown> | void
}) {
  const plain = RISK_PLAIN[ind.riskClass]
  const resolvable = canAct && ind.status === 'open' && SERIOUS.includes(ind.riskClass)

  async function resolve(status: Resolution, reason: string) {
    await api.resolveForensicsIndicator(role, ind.id, { status, reason })
    await onChanged()
  }

  return (
    <div
      className={`rounded-[var(--radius-md)] border border-border border-l-4 bg-white p-3 ${plain.bar}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={plain.tone}>{plain.label}</Badge>
        <span className="text-sm font-medium text-ink">{ind.title}</span>
        {ind.verificationStatus === 'simulated_result' && <Badge tone="neutral">simulated</Badge>}
      </div>
      <p className="mt-1 text-xs text-ink-secondary">{ind.description}</p>
      <dl className="mt-2 grid gap-1 text-[11px] text-ink-muted sm:grid-cols-2">
        <div>
          <dt className="inline font-medium text-ink-secondary">What this means: </dt>
          <dd className="inline">{plain.meaning}</dd>
        </div>
        {ind.affectedPages?.length > 0 && (
          <div>
            <dt className="inline font-medium text-ink-secondary">Pages: </dt>
            <dd className="inline">{ind.affectedPages.join(', ')}</dd>
          </div>
        )}
      </dl>
      {ind.evidence.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-[11px] text-ink-muted">
          {ind.evidence.map((ev) => (
            <li key={ev.id}>
              {ev.description}
              {ev.pageReference ? ` (${ev.pageReference})` : ''}
            </li>
          ))}
        </ul>
      )}
      {resolvable && (
        <ResolveControl
          role={role}
          onResolve={resolve}
          label="Officer note"
        />
      )}
    </div>
  )
}
