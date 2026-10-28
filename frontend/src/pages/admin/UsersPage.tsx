import { useEffect, useState } from 'react'
import { Users } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { DemoBanner } from '@/components/dashboard/DemoBanner'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input, Label, Select } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { AdminInstitution, AdminUser } from '@/types'

export function UsersPage() {
  const { role } = useRole()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [institutions, setInstitutions] = useState<AdminInstitution[]>([])
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    name: '',
    email: '',
    role: 'officer',
    institution_id: '',
  })

  function load() {
    Promise.all([api.listAdminUsers(role), api.listInstitutions(role)])
      .then(([u, i]) => {
        setUsers(u)
        setInstitutions(i)
        setError(null)
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Failed to load users'),
      )
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role])

  return (
    <AppShell title="Users & Roles" breadcrumbs={['Regional Officer', 'Users']}>
      <DemoBanner>
        Create and deactivate demo users. Applicants require an institution. Destructive actions ask
        for confirmation and are audited.
      </DemoBanner>

      {error && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {error}
        </div>
      )}
      {msg && (
        <div className="mb-4 rounded-[var(--radius-md)] border border-emerald-200 bg-status-pass-bg px-3 py-2 text-xs text-status-pass">
          {msg}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title="Add user" description="Roles: applicant, officer, regional_officer" />
          <div className="space-y-3">
            <div>
              <Label>Name</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div>
              <Label>Email</Label>
              <Input
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </div>
            <div>
              <Label>Role</Label>
              <Select
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              >
                <option value="applicant">applicant</option>
                <option value="officer">officer</option>
                <option value="regional_officer">regional_officer</option>
              </Select>
            </div>
            {form.role === 'applicant' && (
              <div>
                <Label>Institution</Label>
                <Select
                  value={form.institution_id}
                  onChange={(e) => setForm((f) => ({ ...f, institution_id: e.target.value }))}
                >
                  <option value="">Select…</option>
                  {institutions.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name}
                    </option>
                  ))}
                </Select>
              </div>
            )}
            <Button
              disabled={busy}
              leftIcon={<Users size={14} />}
              onClick={async () => {
                setBusy(true)
                setMsg(null)
                try {
                  await api.createAdminUser(role, {
                    name: form.name,
                    email: form.email,
                    role: form.role,
                    institution_id: form.role === 'applicant' ? form.institution_id || null : null,
                  })
                  setMsg('User created.')
                  setForm({ name: '', email: '', role: 'officer', institution_id: '' })
                  load()
                } catch (err) {
                  setMsg(err instanceof Error ? err.message : 'Create failed')
                } finally {
                  setBusy(false)
                }
              }}
            >
              Create user
            </Button>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Directory" description={`${users.length} user(s)`} />
          <ul className="divide-y divide-border">
            {users.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div>
                  <div className="text-sm font-medium text-ink">{u.name}</div>
                  <div className="text-xs text-ink-muted">
                    {u.email} · {u.institutionName ?? 'No institution'}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={u.isActive ? 'pass' : 'neutral'}>{u.role}</Badge>
                  {!u.isActive && <Badge tone="warning">inactive</Badge>}
                  {u.isActive && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={async () => {
                        if (!window.confirm(`Deactivate ${u.email}? This is audited.`)) return
                        setBusy(true)
                        try {
                          await api.deactivateAdminUser(role, u.id, 'Deactivated from admin UI')
                          setMsg(`Deactivated ${u.email}`)
                          load()
                        } catch (err) {
                          setMsg(err instanceof Error ? err.message : 'Deactivate failed')
                        } finally {
                          setBusy(false)
                        }
                      }}
                    >
                      Deactivate
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </AppShell>
  )
}
