import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input, Label, Select } from '@/components/ui/Input'
import { Loading, Notice } from '@/components/ui/Notice'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import { RULE_STATUS, RULE_TYPE_LABEL, ruleTypeLabel } from '@/lib/configLabels'
import { formatDateTime } from '@/lib/format'
import type { ConfigCategorySummary, ConfigRule } from '@/types'

/**
 * A filtered view across categories. It reads the same rule records that category pages edit,
 * so it is not a second rule store: every row links to the category that owns the rule.
 */
export function RulesOverviewPage() {
  const { role } = useRole()
  const navigate = useNavigate()
  const [rules, setRules] = useState<ConfigRule[] | null>(null)
  const [categories, setCategories] = useState<ConfigCategorySummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [categoryId, setCategoryId] = useState('')
  const [status, setStatus] = useState('')
  const [ruleType, setRuleType] = useState('')
  const [configVersion, setConfigVersion] = useState('')

  useEffect(() => {
    api
      .cfgListCategories(role)
      .then(setCategories)
      .catch(() => setCategories([]))
  }, [role])

  const load = useCallback(() => {
    setError(null)
    const version = configVersion.trim() === '' ? undefined : Number(configVersion)
    api
      .cfgRulesOverview(role, {
        categoryId: categoryId || undefined,
        status: status || undefined,
        ruleType: ruleType || undefined,
        configVersion: Number.isFinite(version) ? version : undefined,
      })
      .then(setRules)
      .catch((err) => {
        setRules(null)
        setError(err instanceof ApiError ? err.message : 'Rules could not be loaded.')
      })
  }, [role, categoryId, status, ruleType, configVersion])

  useEffect(load, [load])

  const filtered = Boolean(categoryId || status || ruleType || configVersion)

  return (
    <AppShell
      title="Rules & Validation"
      description="Every document rule across categories. Rules are edited from the category that owns them."
      breadcrumbs={['Administration', 'Rules & Validation']}
      actions={
        <Link to="/admin/rules/platform" className="text-sm text-ink-secondary underline">
          Platform-wide regulatory rules
        </Link>
      }
    >
      <div className="mx-auto max-w-7xl">
        <Card padding={false}>
          <div className="grid gap-3 border-b border-border p-4 md:grid-cols-4">
            <div>
              <Label htmlFor="ro-cat">Category</Label>
              <Select id="ro-cat" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
                <option value="">All categories</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="ro-status">Status</Label>
              <Select id="ro-status" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">All</option>
                <option value="active">Active</option>
                <option value="draft">Draft</option>
                <option value="inactive">Inactive</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="ro-type">Rule type</Label>
              <Select id="ro-type" value={ruleType} onChange={(e) => setRuleType(e.target.value)}>
                <option value="">All</option>
                {Object.entries(RULE_TYPE_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="ro-ver">Config version</Label>
              <Input
                id="ro-ver"
                inputMode="numeric"
                value={configVersion}
                onChange={(e) => setConfigVersion(e.target.value.replace(/\D/g, ''))}
                placeholder="Any"
              />
            </div>
          </div>

          {error && (
            <div className="p-4">
              <Notice tone="error" title="Could not load rules" onRetry={load}>
                {error}
              </Notice>
            </div>
          )}
          {!error && rules === null && <Loading label="Loading rules" />}
          {!error && rules?.length === 0 && (
            <div className="p-4">
              <EmptyState
                title={filtered ? 'No rules match these filters' : 'No rules have been created'}
                description={
                  filtered
                    ? 'Clear a filter to widen the view.'
                    : 'Open a category, choose a document and add a rule to start.'
                }
                action={
                  filtered ? (
                    <Button
                      variant="outline"
                      onClick={() => {
                        setCategoryId('')
                        setStatus('')
                        setRuleType('')
                        setConfigVersion('')
                      }}
                    >
                      Clear filters
                    </Button>
                  ) : (
                    <Button onClick={() => navigate('/admin/categories')}>Open categories</Button>
                  )
                }
              />
            </div>
          )}
          {!error && rules && rules.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-xs text-ink-muted">
                  <tr>
                    <th className="px-4 py-2.5 font-medium">Rule</th>
                    <th className="px-3 py-2.5 font-medium">Category</th>
                    <th className="px-3 py-2.5 font-medium">Document</th>
                    <th className="px-3 py-2.5 font-medium">Type</th>
                    <th className="px-3 py-2.5 font-medium">Status</th>
                    <th className="px-3 py-2.5 font-medium">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((r) => {
                    const st = RULE_STATUS[r.status]
                    return (
                      <tr key={r.id} className="h-11 border-b border-border last:border-0 hover:bg-surface">
                        <td className="px-4 py-2.5">
                          <Link to={`/admin/categories/${r.categoryId}`} className="font-medium text-ink hover:underline">
                            {r.title}
                          </Link>
                          <div className="mono text-ink-muted">
                            {r.code}
                            {r.activeVersion != null && ` · v${r.activeVersion}`}
                            {r.configVersion != null && ` · config v${r.configVersion}`}
                          </div>
                        </td>
                        <td className="px-3 py-2.5 text-xs">{r.category?.name ?? '-'}</td>
                        <td className="px-3 py-2.5 text-xs">{r.requirementName ?? r.requirementCode ?? '-'}</td>
                        <td className="px-3 py-2.5 text-xs">{ruleTypeLabel(r.ruleType)}</td>
                        <td className="px-3 py-2.5">
                          <Badge tone={st.tone}>{st.label}</Badge>
                        </td>
                        <td className="px-3 py-2.5 text-xs text-ink-muted">{formatDateTime(r.updatedAt)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  )
}
