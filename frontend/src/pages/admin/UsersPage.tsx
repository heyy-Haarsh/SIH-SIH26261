import { useEffect, useState } from 'react'
import { UserPlus } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { Input, Label, Select } from '@/components/ui/Input'
import { StatusDot } from '@/components/ui/StatusDot'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { api, ApiError } from '@/services/api'
import { useRole } from '@/app/RoleContext'
import type { AdminInstitution, AdminUser } from '@/types'

const ROLE_LABELS: Record<string, string> = {
  applicant: 'Applicant',
  officer: 'Scrutiny Officer',
  regional_officer: 'Regional Officer',
}

export function UsersPage() {
  const { role } = useRole()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [institutions, setInstitutions] = useState<AdminInstitution[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    name: '',
    email: '',
    role: 'officer',
    institution_id: '',
  })
  const [showForm, setShowForm] = useState(false)
  const [search, setSearch] = useState('')

  function load() {
    setLoading(true)
    Promise.all([api.listAdminUsers(role), api.listInstitutions(role)])
      .then(([u, i]) => {
        setUsers(u)
        setInstitutions(i)
        setError(null)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load users'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [role]) // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = users.filter(
    (u) =>
      !search ||
      u.name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      u.role.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <AppShell
      title="Users & Roles"
      description="Create and manage system users · Applicants require an institution · All destructive actions are audited."
      breadcrumbs={['Regional Officer', 'Users']}
      actions={
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white transition-colors"
          style={{ background: '#E8622A' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = '#D4541F')}
          onMouseLeave={(e) => (e.currentTarget.style.background = '#E8622A')}
        >
          <UserPlus size={14} />
          {showForm ? 'Cancel' : 'Add User'}
        </button>
      }
    >
      {/* Feedback banners */}
      {error && (
        <div
          className="mb-5 rounded-xl px-4 py-3 text-sm"
          style={{ background: '#FEF3C7', color: '#B45309', border: '1px solid #FDE68A' }}
        >
          {error}
        </div>
      )}
      {msg && (
        <div
          className="mb-5 rounded-xl px-4 py-3 text-sm"
          style={{ background: '#F0FDF4', color: '#166534', border: '1px solid #BBF7D0' }}
        >
          {msg}
        </div>
      )}

      {/* ── Add user form (collapsible) ─────────────── */}
      {showForm && (
        <div
          className="rounded-xl p-6 mb-5"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <div className="text-sm font-semibold mb-4" style={{ color: '#111111' }}>
            Create New User
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <Label htmlFor="u-name">Full name</Label>
              <Input
                id="u-name"
                placeholder="Jane Smith"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="u-email">Email</Label>
              <Input
                id="u-email"
                type="email"
                placeholder="jane@example.com"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="u-role">Role</Label>
              <Select
                id="u-role"
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              >
                <option value="applicant">Applicant</option>
                <option value="officer">Scrutiny Officer</option>
                <option value="regional_officer">Regional Officer</option>
              </Select>
            </div>
            {form.role === 'applicant' && (
              <div>
                <Label htmlFor="u-inst">Institution</Label>
                <Select
                  id="u-inst"
                  value={form.institution_id}
                  onChange={(e) => setForm((f) => ({ ...f, institution_id: e.target.value }))}
                >
                  <option value="">Select…</option>
                  {institutions.map((i) => (
                    <option key={i.id} value={i.id}>{i.name}</option>
                  ))}
                </Select>
              </div>
            )}
          </div>
          <div className="mt-4">
            <Button
              disabled={busy}
              leftIcon={<UserPlus size={14} />}
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
                  setMsg(`User "${form.name}" created.`)
                  setForm({ name: '', email: '', role: 'officer', institution_id: '' })
                  setShowForm(false)
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
        </div>
      )}

      {/* ── User directory table ─────────────────────── */}
      <div
        className="rounded-xl overflow-hidden"
        style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
      >
        {/* Table toolbar */}
        <div
          className="flex items-center justify-between gap-4 px-6 py-3"
          style={{ borderBottom: '1px solid #F0F0F0' }}
        >
          <div className="text-sm font-semibold" style={{ color: '#111111' }}>
            Directory
            <span className="ml-2 text-[12px] font-normal" style={{ color: '#888888' }}>
              {filtered.length} of {users.length} user{users.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div
            className="flex items-center gap-2 rounded-lg border px-3 py-1.5"
            style={{ border: '1px solid #E0E0E0', background: '#FAFAFA' }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#AAAAAA" strokeWidth="2">
              <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
            </svg>
            <input
              type="text"
              placeholder="Search by name, email, role…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-48 bg-transparent text-xs outline-none"
              style={{ color: '#333333' }}
              aria-label="Search users"
            />
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr style={{ borderBottom: '1px solid #F0F0F0' }}>
                {['Name', 'Email', 'Role', 'Institution', 'Status', ''].map((col) => (
                  <th
                    key={col}
                    className="px-6 py-3 text-[11px] font-semibold uppercase tracking-wider"
                    style={{ color: '#AAAAAA' }}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <SkeletonTable rows={4} cols={6} />
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-sm" style={{ color: '#AAAAAA' }}>
                    {search ? 'No users match that search.' : 'No users found.'}
                  </td>
                </tr>
              ) : (
                filtered.map((u) => (
                  <tr
                    key={u.id}
                    className="transition-colors hover:bg-[#FAFAFA]"
                    style={{ borderBottom: '1px solid #F0F0F0' }}
                  >
                    <td className="px-6 py-4 text-sm font-medium" style={{ color: '#111111' }}>
                      {u.name}
                    </td>
                    <td className="px-6 py-4 text-[12px]" style={{ color: '#555555' }}>
                      {u.email}
                    </td>
                    <td className="px-6 py-4 text-[12px]" style={{ color: '#555555' }}>
                      {ROLE_LABELS[u.role] ?? u.role}
                    </td>
                    <td className="px-6 py-4 text-[12px]" style={{ color: '#888888' }}>
                      {u.institutionName ?? '—'}
                    </td>
                    <td className="px-6 py-4">
                      <StatusDot
                        status={u.isActive ? 'pass' : 'neutral'}
                        label={u.isActive ? 'Active' : 'Inactive'}
                      />
                    </td>
                    <td className="px-6 py-4 text-right">
                      {u.isActive &&
                        !['usr-app-001', 'usr-off-001', 'usr-off-002', 'usr-adm-001'].includes(u.id) && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={async () => {
                              if (!window.confirm(`Deactivate ${u.email}? This action is audited.`)) return
                              setBusy(true)
                              try {
                                await api.deactivateAdminUser(role, u.id, 'Deactivated from admin UI')
                                setMsg(`Deactivated ${u.email}.`)
                                load()
                              } catch (err) {
                                setMsg(err instanceof Error ? err.message : 'Deactivate failed')
                              } finally {
                                setBusy(false)
                              }
                            }}
                            className="rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40"
                            style={{ border: '1px solid #E0E0E0', color: '#B91C1C' }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = '#FEF2F2')}
                            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                          >
                            Deactivate
                          </button>
                        )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  )
}
