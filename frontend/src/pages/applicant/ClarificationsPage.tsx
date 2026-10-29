import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Label, Textarea } from '@/components/ui/Input'
import { Loading, Notice } from '@/components/ui/Notice'
import { SkeletonDetailLayout } from '@/components/ui/Skeleton'
import { StatusDot } from '@/components/ui/StatusDot'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { CLARIFICATION_STATE } from '@/lib/applicantLifecycle'
import { formatDateTime, formatRelative } from '@/lib/format'
import type { ApplicantDeficiency, ClarificationState, ResponseMode } from '@/types'

type Filter = 'all' | ClarificationState

const FILTERS: Array<{ id: Filter; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'action_required', label: 'Action Required' },
  { id: 'response_saved', label: 'Response Saved' },
  { id: 'awaiting_review', label: 'Awaiting Review' },
  { id: 'resolved', label: 'Resolved' },
]

const MODES: Array<{ id: ResponseMode; label: string; hint: string }> = [
  { id: 'text', label: 'Text only', hint: 'Explain without a new file.' },
  { id: 'document', label: 'Document only', hint: 'Replace a file on the application.' },
  { id: 'both', label: 'Text and document', hint: 'Explain and replace a file.' },
]

function stateOf(item: ApplicantDeficiency): ClarificationState {
  return (item.applicantState ?? (item.status === 'open' ? 'action_required' : 'resolved')) as ClarificationState
}

export function ClarificationsPage() {
  const { role } = useRole()
  const [items, setItems] = useState<ApplicantDeficiency[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  function load() {
    setError(null)
    api
      .listMyClarifications(role)
      .then((data) => {
        setItems(data)
        // Auto-select first action-required
        const first = data.find((d) => stateOf(d) === 'action_required') ?? data[0]
        if (first && !selectedId) setSelectedId(first.id)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Clarifications could not be loaded.'))
  }

  useEffect(() => {
    if (role === 'applicant') load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role])

  const counts = useMemo(() => {
    const base: Record<Filter, number> = {
      all: items?.length ?? 0,
      action_required: 0,
      response_saved: 0,
      awaiting_review: 0,
      resolved: 0,
    }
    for (const item of items ?? []) base[stateOf(item)] += 1
    return base
  }, [items])

  const filtered = useMemo(() => {
    if (!items) return []
    if (filter === 'all') return items
    return items.filter((d) => stateOf(d) === filter)
  }, [items, filter])

  const selected = filtered.find((d) => d.id === selectedId) ?? filtered[0] ?? null

  return (
    <AppShell
      title="Clarifications"
      description="Requests from the scrutiny officer · Respond here, then resubmit your application."
      breadcrumbs={['Applicant', 'Clarifications']}
    >
      {error && (
        <Notice tone="error" className="mb-6" title="Could not load clarifications" onRetry={load}>
          {error}
        </Notice>
      )}
      {items === null && !error && <SkeletonDetailLayout />}

      {items?.length === 0 && (
        <div
          className="rounded-xl"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <EmptyState
            title="No clarification requests"
            description="When an officer asks for something, it will appear here."
          />
        </div>
      )}

      {items && items.length > 0 && (
        <>
          {/* Tab filter row */}
          <div
            className="flex items-center gap-0 mb-4 rounded-xl overflow-hidden"
            style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
          >
            <div
              className="flex items-center px-4 pt-1"
              style={{ borderBottom: '1px solid #F0F0F0', width: '100%' }}
            >
              {FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setFilter(f.id)}
                  className={`flex items-center gap-1.5 px-4 py-3.5 text-sm transition-colors ${
                    filter === f.id ? 'tab-active' : 'tab-inactive'
                  }`}
                >
                  {f.label}
                  <span
                    className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none"
                    style={{
                      background: filter === f.id ? '#111111' : '#F0F0F0',
                      color: filter === f.id ? '#FFFFFF' : '#888888',
                    }}
                  >
                    {counts[f.id]}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Master-detail split */}
          <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)] items-start">
            {/* Left: Item list */}
            <div
              className="rounded-xl overflow-hidden"
              style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
            >
              {filtered.length === 0 ? (
                <p className="px-5 py-8 text-sm text-center" style={{ color: '#AAAAAA' }}>
                  Nothing in this filter.
                </p>
              ) : (
                <ul>
                  {filtered.map((d) => {
                    const st = CLARIFICATION_STATE[stateOf(d)] ?? CLARIFICATION_STATE.action_required
                    const isActive = selected?.id === d.id
                    return (
                      <li key={d.id} style={{ borderBottom: '1px solid #F0F0F0' }}>
                        <button
                          type="button"
                          onClick={() => setSelectedId(d.id)}
                          aria-current={isActive ? 'true' : undefined}
                          className="w-full px-4 py-3.5 text-left transition-colors"
                          style={{
                            background: isActive ? '#F8F8F8' : 'transparent',
                            borderLeft: isActive ? '2px solid #E8622A' : '2px solid transparent',
                          }}
                          onMouseEnter={(e) => {
                            if (!isActive) e.currentTarget.style.background = '#FAFAFA'
                          }}
                          onMouseLeave={(e) => {
                            if (!isActive) e.currentTarget.style.background = 'transparent'
                          }}
                        >
                          <span className="block truncate text-sm font-medium" style={{ color: '#111111' }}>
                            {d.title}
                          </span>
                          <span className="mono mt-0.5 block text-[11px]" style={{ color: '#888888' }}>
                            {d.applicationNumber}
                          </span>
                          <span className="mt-2 flex items-center justify-between">
                            <StatusDot status={stateOf(d)} label={st.label} />
                            <span className="text-[10px]" style={{ color: '#AAAAAA' }}>
                              {formatRelative(d.createdAt)}
                            </span>
                          </span>
                          {d.requiresReplacement && (
                            <span
                              className="mt-1 block text-[10px] font-medium"
                              style={{ color: '#E8622A' }}
                            >
                              ⚠ Replacement required
                            </span>
                          )}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>

            {/* Right: Detail panel */}
            {selected ? (
              <ClarificationDetail key={selected.id} item={selected} onChanged={load} />
            ) : (
              <div
                className="rounded-xl"
                style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
              >
                <EmptyState
                  title="Select a request"
                  description="Choose a clarification from the list to see details and respond."
                />
              </div>
            )}
          </div>
        </>
      )}
    </AppShell>
  )
}

function ClarificationDetail({ item, onChanged }: { item: ApplicantDeficiency; onChanged: () => void }) {
  const { role } = useRole()
  const [mode, setMode] = useState<ResponseMode>(item.requiresReplacement ? 'both' : 'text')
  const [text, setText] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const st = CLARIFICATION_STATE[stateOf(item)] ?? CLARIFICATION_STATE.action_required
  const open = item.status === 'open'
  const history = item.responses ?? []

  async function save() {
    if (item.requiresReplacement && mode === 'text') {
      setError('This request needs a replacement document. A text reply alone cannot close it.')
      return
    }
    if (!confirm) {
      setError('Review the preview and confirm before sending.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.respondDeficiency(role, item.id, text.trim())
      setNote(
        item.requiresReplacement
          ? 'Response saved. Upload the replacement on the application, then resubmit.'
          : 'Response saved. Resubmit the application so the officer can see it.',
      )
      setText('')
      setConfirm(false)
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The response could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
    >
      {/* Header */}
      <div className="px-6 py-5" style={{ borderBottom: '1px solid #F0F0F0' }}>
        <div className="flex items-start justify-between gap-4 mb-2">
          <h2 className="text-base font-semibold" style={{ color: '#111111' }}>
            {item.title}
          </h2>
          <StatusDot status={stateOf(item)} label={st.label} />
        </div>
        <div className="text-[12px] mb-3" style={{ color: '#888888' }}>
          <span className="mono">{item.applicationNumber}</span>
          {item.requestedBy ? ` · ${item.requestedBy}` : ''}
          {item.dueDate ? ` · Due ${formatDateTime(item.dueDate)}` : ''}
          {' · '}{formatRelative(item.createdAt)}
        </div>
        <p className="text-sm leading-relaxed" style={{ color: '#555555' }}>
          {item.description}
        </p>
        {item.linkedItems && item.linkedItems.length > 0 && (
          <ul className="mt-3 space-y-1">
            {item.linkedItems.map((linked) => (
              <li key={`${linked.documentName}:${linked.summary}`} className="text-[12px]" style={{ color: '#555555' }}>
                <span className="font-medium" style={{ color: '#333333' }}>{linked.documentName}</span>
                {linked.summary ? ` — ${linked.summary}` : ''}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Response form */}
      <div className="px-6 py-5 space-y-5">
        {item.requiresReplacement && (
          <div
            className="rounded-lg px-4 py-3 text-sm"
            style={{ background: '#FFFBEB', border: '1px solid #FDE68A', color: '#92400E' }}
          >
            A replacement document is required. A text-only reply cannot satisfy this request, and uploading a file does not mark it resolved on its own.
          </div>
        )}

        {open && (
          <section className="space-y-4">
            <div className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: '#AAAAAA' }}>
              Your Response
            </div>

            {/* Mode selector */}
            <div className="grid gap-2 sm:grid-cols-3">
              {MODES.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setMode(m.id)}
                  aria-pressed={mode === m.id}
                  className="rounded-lg border px-3 py-2.5 text-left transition-colors"
                  style={{
                    border: mode === m.id ? '1px solid #E8622A' : '1px solid #E0E0E0',
                    background: mode === m.id ? '#FEF2EC' : 'transparent',
                  }}
                >
                  <span
                    className="block text-sm font-medium"
                    style={{ color: mode === m.id ? '#E8622A' : '#111111' }}
                  >
                    {m.label}
                  </span>
                  <span className="mt-0.5 block text-[11px]" style={{ color: '#888888' }}>
                    {m.hint}
                  </span>
                </button>
              ))}
            </div>

            {(mode === 'text' || mode === 'both') && (
              <div>
                <Label htmlFor="cl-text">Your explanation</Label>
                <Textarea
                  id="cl-text"
                  rows={5}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Explain clearly what you are providing or correcting…"
                />
              </div>
            )}

            {(mode === 'document' || mode === 'both' || item.requiresReplacement) && (
              <p className="text-[12px]" style={{ color: '#888888' }}>
                Upload the replacement document from the application page. This inbox does not replace files directly.
              </p>
            )}

            {/* Preview */}
            <div
              className="rounded-lg px-4 py-3"
              style={{ background: '#FAFAFA', border: '1px solid #F0F0F0' }}
            >
              <div className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: '#AAAAAA' }}>
                Preview
              </div>
              <p className="text-sm" style={{ color: text.trim() ? '#333333' : '#AAAAAA' }}>
                {text.trim() || 'No text entered.'}
              </p>
              {item.requiresReplacement && (
                <p className="mt-2 text-[11px]" style={{ color: '#B45309' }}>
                  Replacement document still required on the application.
                </p>
              )}
            </div>

            {/* Confirm */}
            <label className="flex items-start gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                className="mt-0.5 rounded accent-[#E8622A]"
                checked={confirm}
                onChange={(e) => setConfirm(e.target.checked)}
              />
              <span className="text-sm" style={{ color: '#555555' }}>
                I have reviewed this response and want to save it.
              </span>
            </label>

            {error && <Notice tone="error">{error}</Notice>}
            {note && <Notice tone="success">{note}</Notice>}

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void save()} disabled={busy}>
                {busy ? 'Saving…' : 'Save response'}
              </Button>
              <Link to={`/applicant/applications/${item.applicationId}`}>
                <Button variant="outline">Open application</Button>
              </Link>
            </div>
          </section>
        )}

        {!open && (
          <div className="flex flex-wrap gap-2">
            <Link to={`/applicant/applications/${item.applicationId}`}>
              <Button variant="outline">Open application</Button>
            </Link>
          </div>
        )}

        {/* History */}
        {(history.length > 0 || item.applicantResponse) && (
          <section style={{ borderTop: '1px solid #F0F0F0', paddingTop: '1.25rem' }}>
            <div className="text-[11px] font-semibold uppercase tracking-widest mb-3" style={{ color: '#AAAAAA' }}>
              Response History
            </div>
            <ul className="space-y-2">
              {history.map((r) => (
                <li
                  key={r.id}
                  className="rounded-lg px-4 py-3 text-sm"
                  style={{ background: '#FAFAFA', border: '1px solid #F0F0F0', color: '#555555' }}
                >
                  <div className="text-[11px] mb-1" style={{ color: '#AAAAAA' }}>
                    {formatDateTime(r.createdAt)}
                  </div>
                  {r.text || '(document only)'}
                </li>
              ))}
              {history.length === 0 && item.applicantResponse && (
                <li
                  className="rounded-lg px-4 py-3 text-sm"
                  style={{ background: '#FAFAFA', border: '1px solid #F0F0F0', color: '#555555' }}
                >
                  {item.applicantResponse}
                </li>
              )}
            </ul>
          </section>
        )}
      </div>
    </div>
  )
}
