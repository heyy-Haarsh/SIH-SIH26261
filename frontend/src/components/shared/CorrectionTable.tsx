export interface CorrectionRow {
  documentName?: string | null
  action: string
  status?: string | null
}

export interface GroupedCorrection {
  documentName: string
  actions: string[]
}

export function groupCorrectionRows(rows: CorrectionRow[]): GroupedCorrection[] {
  const groups: GroupedCorrection[] = []
  const index = new Map<string, number>()
  for (const row of rows) {
    const name = (row.documentName || 'Application').trim() || 'Application'
    const action = row.action.trim()
    if (!action) continue
    const existing = index.get(name.toLowerCase())
    if (existing === undefined) {
      index.set(name.toLowerCase(), groups.length)
      groups.push({ documentName: name, actions: [action] })
      continue
    }
    if (!groups[existing].actions.includes(action)) {
      groups[existing].actions.push(action)
    }
  }
  return groups
}

/** Turn a stored officer paragraph into document / action rows. */
export function rowsFromOfficerText(text: string | null | undefined): CorrectionRow[] {
  if (!text?.trim()) return []
  const lines = text
    .split(/\n+|(?:;\s*(?=[A-Z][^:]{2,70}:\s))|(?:\s[-–]\s(?=[A-Z][^:]{2,70}:\s))/)
    .map((l) => l.replace(/^[\s\-–•*\d.]+/, '').trim())
    .filter((l) => l && !/^the application cannot be recommended/i.test(l))
    .filter((l) => !/^see the correction list/i.test(l))
  const rows: CorrectionRow[] = []
  for (const line of lines) {
    const cut = line.indexOf(': ')
    if (cut > 0 && cut < 80) {
      rows.push({ documentName: line.slice(0, cut), action: line.slice(cut + 2) })
    } else {
      rows.push({ documentName: 'Application', action: line })
    }
  }
  return rows
}

export function CorrectionTable({
  rows,
  empty = 'Nothing for the applicant to correct.',
}: {
  rows: CorrectionRow[]
  empty?: string
}) {
  const groups = groupCorrectionRows(rows)
  if (groups.length === 0) {
    return empty ? <p className="text-xs text-ink-muted">{empty}</p> : null
  }
  return (
    <div className="overflow-x-auto rounded-[var(--radius-md)] border border-border">
      <table className="w-full min-w-[480px] text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            <th className="w-10 px-3 py-2">#</th>
            <th className="w-[34%] px-3 py-2">Document</th>
            <th className="px-3 py-2">What to do</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group, i) => (
            <tr key={`${group.documentName}-${i}`} className="border-b border-border last:border-0">
              <td className="px-3 py-2.5 align-top text-xs text-ink-muted">{i + 1}</td>
              <td className="px-3 py-2.5 align-top font-medium text-ink">{group.documentName}</td>
              <td className="px-3 py-2.5 align-top text-ink-secondary">
                {group.actions.length === 1 ? (
                  group.actions[0]
                ) : (
                  <ol className="list-decimal space-y-1 pl-4">
                    {group.actions.map((action) => (
                      <li key={action}>{action}</li>
                    ))}
                  </ol>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function OfficerUpdateTable({
  rows,
  empty = 'No officer updates yet.',
}: {
  rows: Array<{
    documentName?: string | null
    issue: string
    status: string
    statusLabel?: string | null
    note: string
  }>
  empty?: string
}) {
  if (rows.length === 0) {
    return <p className="text-xs text-ink-muted">{empty}</p>
  }
  return (
    <div className="overflow-x-auto rounded-[var(--radius-md)] border border-border">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            <th className="px-3 py-2">Document</th>
            <th className="px-3 py-2">Issue</th>
            <th className="px-3 py-2">Officer decision</th>
            <th className="px-3 py-2">Officer note</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={`${row.issue}-${i}`} className="border-b border-border last:border-0 align-top">
              <td className="px-3 py-2.5 font-medium text-ink">{row.documentName || 'Application'}</td>
              <td className="px-3 py-2.5 text-ink-secondary">{row.issue}</td>
              <td className="px-3 py-2.5 capitalize text-ink">{row.status}</td>
              <td className="px-3 py-2.5 text-ink-secondary">
                <div>{row.note}</div>
                {row.statusLabel && (
                  <div className="mt-1 text-[11px] text-ink-muted">{row.statusLabel}</div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
