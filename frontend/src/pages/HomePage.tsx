import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Building2,
  Eye,
  EyeOff,
  FileCheck2,
  Lock,
  Mail,
  Network,
  PlayCircle,
  Scale,
  ScrollText,
  ShieldCheck,
  UserRound,
} from 'lucide-react'
import { useRole } from '@/app/RoleContext'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import type { DemoPersona } from '@/lib/demoAuthSession'
import { DEMO_CREDENTIALS, DEMO_PASSWORD, matchDemoCredential } from '@/lib/demoCredentials'
import { PROTOTYPE_VIDEO_URL } from '@/lib/prototypeLinks'
import { ROLE_HOME } from '@/lib/nav'

const NAV_LINKS = [
  { label: 'Home', href: '#login' },
  { label: 'About', href: '#features' },
  { label: 'Approval Process', href: '#features' },
  { label: 'Resources', href: '#features' },
  { label: 'Video prototype', href: PROTOTYPE_VIDEO_URL, external: true },
  { label: 'Help & Support', href: '#login' },
] as const

const PERSONA_ICONS: Record<DemoPersona, typeof Building2> = {
  applicant: Building2,
  officer: UserRound,
  officer_2: UserRound,
  regional_officer: Network,
}

export function HomePage() {
  const { role, isLoggedIn, login } = useRole()
  const navigate = useNavigate()
  const [selectedPersona, setSelectedPersona] = useState<DemoPersona>('applicant')
  const [email, setEmail] = useState(DEMO_CREDENTIALS[0].email)
  const [password, setPassword] = useState(DEMO_PASSWORD)
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (isLoggedIn) {
    return <Navigate to={ROLE_HOME[role]} replace />
  }

  function fill(persona: DemoPersona) {
    const cred = DEMO_CREDENTIALS.find((c) => c.persona === persona)
    if (!cred) return
    setSelectedPersona(persona)
    setEmail(cred.email)
    setPassword(cred.password)
    setError(null)
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const matched = matchDemoCredential(email, password)
    if (!matched) {
      setError('Use a demo account — password is demo@123 for all roles.')
      setBusy(false)
      return
    }
    login(matched.persona)
    navigate(ROLE_HOME[matched.role], { replace: true })
  }

  return (
    <div className="min-h-full bg-white">
      {/* Top letterhead */}
      <header className="border-b border-[#E8EEF5] bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <img
              src="/aicte-logo.png"
              alt="AICTE"
              width={52}
              height={52}
              className="h-12 w-12 shrink-0 object-contain sm:h-13 sm:w-13"
            />
            <div className="min-w-0 leading-tight">
              <p className="text-[13px] font-bold text-[#0B3A6E] sm:text-[15px]">
                All India Council for Technical Education
              </p>
              <p className="text-[12px] font-medium text-[#555555]">
                अखिल भारतीय तकनीकी शिक्षा परिषद्
              </p>
            </div>
          </div>

          <nav className="hidden items-center gap-4 xl:gap-5 lg:flex" aria-label="Primary">
            {NAV_LINKS.map((item) => (
              <a
                key={item.label}
                href={item.href}
                {...('external' in item && item.external
                  ? { target: '_blank', rel: 'noopener noreferrer' }
                  : {})}
                className={
                  item.label === 'Home'
                    ? 'border-b-2 border-[#E8622A] pb-0.5 text-[13px] font-semibold text-[#0B3A6E]'
                    : item.label === 'Video prototype'
                      ? 'text-[13px] font-semibold text-[#E8622A] hover:underline'
                      : 'text-[13px] font-medium text-[#555555] hover:text-[#0B3A6E]'
                }
              >
                {item.label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-2.5">
            <img
              src="/india-emblem.svg"
              alt=""
              width={40}
              height={56}
              className="h-12 w-auto object-contain"
            />
            <div className="hidden text-right leading-tight sm:block">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-[#0B3A6E]">
                Government of India
              </p>
              <p className="text-[11px] text-[#555555]">भारत सरकार</p>
            </div>
          </div>
        </div>
      </header>

      {/* Hero: AICTE HQ photo + login */}
      <section
        id="login"
        className="relative overflow-hidden"
        style={{
          backgroundImage:
            'linear-gradient(90deg, rgba(245,248,252,0.94) 0%, rgba(245,248,252,0.82) 42%, rgba(245,248,252,0.35) 70%, rgba(245,248,252,0.15) 100%), url(/aicte-hq.jpg)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 40%',
        }}
      >
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-10 lg:grid-cols-[1.15fr_0.85fr] lg:items-center lg:py-14">
          <div className="max-w-xl">
            <span
              className="inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-white"
              style={{ background: '#E8622A' }}
            >
              PRAMAN
            </span>
            <h1 className="mt-3 text-3xl font-bold leading-tight tracking-tight text-[#0B3A6E] sm:text-4xl">
              PRAMAN{' '}
              <span className="text-[#111111]">AICTE Compliance Platform</span>
            </h1>
            <p className="mt-2 text-base font-semibold text-[#E8622A]">
              Transparent. Efficient. Compliant.
            </p>
            <p className="mt-3 text-sm leading-relaxed text-[#333333]">
              An AI-powered platform for submission, verification and monitoring of approval
              applications for technical institutions under AICTE.
            </p>

            <ul className="mt-5 flex flex-wrap gap-2">
              {[
                { icon: Building2, label: '10,000+ Institutions' },
                { icon: FileCheck2, label: 'Faster Processing' },
                { icon: ShieldCheck, label: 'Authentic Verification' },
                { icon: BarChart3, label: 'Transparent Governance' },
              ].map(({ icon: Icon, label }) => (
                <li
                  key={label}
                  className="inline-flex items-center gap-1.5 rounded-full bg-white/95 px-3 py-1.5 text-[12px] font-medium text-[#0B3A6E]"
                  style={{ border: '1px solid #D6E4F5', boxShadow: '0 1px 2px rgba(11,58,110,0.06)' }}
                >
                  <Icon size={13} className="text-[#E8622A]" />
                  {label}
                </li>
              ))}
            </ul>

            <div className="mt-6">
              <a
                href={PROTOTYPE_VIDEO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-xl bg-[#0B3A6E] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#0A2F58]"
              >
                <PlayCircle size={18} className="text-[#E8622A]" />
                View video prototype
              </a>
              <p className="mt-2 text-[11px] text-[#555555]">
                Opens the product walkthrough in a new tab.
              </p>
            </div>
          </div>

          {/* Login card */}
          <div
            className="rounded-2xl bg-white p-5 sm:p-6"
            style={{ border: '1px solid #D6E4F5', boxShadow: '0 12px 40px rgba(11,58,110,0.12)' }}
          >
            <h2 className="text-base font-bold text-[#0B3A6E]">Login to PRAMAN</h2>
            <p className="mt-0.5 text-[12px] text-[#555555]">Select your role to continue</p>

            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {DEMO_CREDENTIALS.map((c) => {
                const Icon = PERSONA_ICONS[c.persona]
                const active = selectedPersona === c.persona
                return (
                  <button
                    key={c.persona}
                    type="button"
                    onClick={() => fill(c.persona)}
                    className="flex flex-col items-center gap-1.5 rounded-xl px-2 py-2.5 text-center transition-colors"
                    style={{
                      background: active ? '#EFF6FF' : '#F8FAFC',
                      border: `1.5px solid ${active ? '#1D4ED8' : '#E2E8F0'}`,
                      color: active ? '#1D4ED8' : '#555555',
                    }}
                  >
                    <Icon size={16} />
                    <span className="text-[10px] font-semibold leading-tight">{c.label}</span>
                  </button>
                )
              })}
            </div>

            <form className="mt-4 space-y-3" onSubmit={onSubmit} autoComplete="on">
              <div>
                <label className="mb-1 block text-[11px] font-semibold text-[#555555]" htmlFor="login-email">
                  Email
                </label>
                <div className="relative">
                  <Mail size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#888888]" />
                  <Input
                    id="login-email"
                    name="username"
                    type="email"
                    autoComplete="username"
                    className="!pl-9"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your official email ID"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-[11px] font-semibold text-[#555555]" htmlFor="login-password">
                  Password
                </label>
                <div className="relative">
                  <Lock size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#888888]" />
                  <Input
                    id="login-password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    className="!pl-9 !pr-10"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    required
                  />
                  <button
                    type="button"
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-[#888888] hover:text-[#111111]"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-[#888888]">
                  Demo password: <span className="font-mono text-[#111111]">{DEMO_PASSWORD}</span>
                </p>
              </div>

              <div className="flex items-center justify-between gap-2 text-[12px]">
                <label className="flex items-center gap-1.5 text-[#555555]">
                  <input
                    type="checkbox"
                    className="accent-[#1D4ED8]"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                  />
                  Remember me
                </label>
                <span className="font-medium text-[#1D4ED8]">Forgot password?</span>
              </div>

              {error && (
                <p className="rounded-lg bg-[#FEE2E2] px-3 py-2 text-xs text-[#B91C1C]" role="alert">
                  {error}
                </p>
              )}

              <Button
                type="submit"
                className="w-full !bg-[#1D4ED8] hover:!bg-[#1E40AF]"
                disabled={busy}
              >
                {busy ? 'Signing in…' : 'Sign in to PRAMAN →'}
              </Button>
            </form>

            <p
              className="mt-4 rounded-lg px-3 py-2 text-[11px] leading-relaxed text-[#1E3A5F]"
              style={{ background: '#EFF6FF', border: '1px solid #BFDBFE' }}
            >
              Use your AICTE-provided credentials. For the demo, click a role above to auto-fill.
            </p>
          </div>
        </div>
      </section>

      {/* Key features */}
      <section id="features" className="border-y border-[#E8EEF5] bg-white">
        <div className="mx-auto max-w-7xl px-5 py-8">
          <h2 className="text-center text-sm font-bold uppercase tracking-widest text-[#0B3A6E]">
            Key Features
          </h2>
          <ul className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: FileCheck2,
                title: 'AI-Powered Document Verification',
                text: 'OCR, classification and rule-based compliance checks.',
                color: '#1D4ED8',
                bg: '#EFF6FF',
              },
              {
                icon: Network,
                title: 'Multi-Role Workflow',
                text: 'Submit, review, verify and monitor applications.',
                color: '#0B3A6E',
                bg: '#E8EEF5',
              },
              {
                icon: Scale,
                title: 'Regulatory Compliance',
                text: 'Aligned with AICTE handbook and approval process.',
                color: '#2E7D52',
                bg: '#EBF5EF',
              },
              {
                icon: ScrollText,
                title: 'Audit and Traceability',
                text: 'Complete audit trail and real-time status tracking.',
                color: '#E8622A',
                bg: '#FEF2EC',
              },
            ].map(({ icon: Icon, title, text, color, bg }) => (
              <li key={title} className="rounded-xl border border-[#E8EEF5] bg-[#FAFBFC] p-4">
                <span
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg"
                  style={{ background: bg, color }}
                >
                  <Icon size={18} />
                </span>
                <p className="mt-2.5 text-sm font-semibold text-[#111111]">{title}</p>
                <p className="mt-1 text-[12px] leading-relaxed text-[#555555]">{text}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <footer className="bg-[#0B3A6E] text-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-semibold">PRAMAN · AICTE Compliance Platform</p>
          <nav className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-white/80">
            <span>About AICTE</span>
            <span>Privacy Policy</span>
            <span>Terms of Use</span>
            <span>Help &amp; Support</span>
          </nav>
          <p className="text-[11px] text-white/70">
            © 2026 All India Council for Technical Education. Government of India.
          </p>
        </div>
        <p className="border-t border-white/10 px-5 py-2 text-center text-[10px] text-white/50">
          Headquarters photo: AICTE Head Office, Vasant Kunj, New Delhi (Wikimedia Commons, CC BY-SA 4.0).
        </p>
      </footer>
    </div>
  )
}
