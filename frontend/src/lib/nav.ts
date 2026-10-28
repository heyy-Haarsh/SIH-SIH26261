import {
  Activity,
  AlertTriangle,
  BookOpen,
  Building2,
  FolderOpen,
  GitCompare,
  HeartPulse,
  LayoutDashboard,
  ListChecks,
  Plug,
  FilePlus2,
  Scale,
  Settings,
  Upload,
  Users,
  Workflow,
  type LucideIcon,
} from 'lucide-react'
import type { UserRole } from '@/types'

export interface NavItem {
  label: string
  path: string
  icon: LucideIcon
  /** Optional group heading shown above the first item of a group. */
  section?: string
  /** Optional badge key resolved by the sidebar (e.g. newDelegations). */
  badgeKey?: string
}

export const ROLE_HOME: Record<UserRole, string> = {
  applicant: '/applicant',
  officer: '/officer',
  regional_officer: '/admin',
}

/**
 * Every entry points at a real, working page. Detail views (documents, extracted data,
 * findings, reports, decisions) live inside an application so they are not duplicated here.
 */
export const NAV_BY_ROLE: Record<UserRole, NavItem[]> = {
  applicant: [
    { label: 'Dashboard', path: '/applicant', icon: LayoutDashboard, section: 'My work' },
    { label: 'My Applications', path: '/applicant/applications', icon: FolderOpen },
    { label: 'New Application', path: '/applicant/applications/new', icon: FilePlus2 },
    { label: 'Upload Documents', path: '/applicant/uploads', icon: Upload },
    { label: 'Clarifications', path: '/applicant/deficiencies', icon: AlertTriangle },
  ],
  officer: [
    { label: 'Overview', path: '/officer', icon: LayoutDashboard, section: 'Scrutiny' },
    {
      label: 'Application Queue',
      path: '/officer/queue',
      icon: FolderOpen,
      badgeKey: 'myQueue',
    },
    { label: 'Cross-document Review', path: '/officer/comparison', icon: GitCompare },
  ],
  regional_officer: [
    { label: 'Overview', path: '/admin', icon: LayoutDashboard, section: 'Operations' },
    {
      label: 'Delegation Queue',
      path: '/admin/delegation',
      icon: Workflow,
      badgeKey: 'unassigned',
    },
    { label: 'System Health', path: '/admin/health', icon: HeartPulse },
    { label: 'Audit Trail', path: '/admin/audit', icon: Activity },
    { label: 'Integrations', path: '/admin/integrations', icon: Plug },
    { label: 'Regulatory Rules', path: '/admin/rules', icon: Scale, section: 'Verification rules' },
    { label: 'Handbook References', path: '/admin/handbook', icon: BookOpen },
    { label: 'Users & Roles', path: '/admin/users', icon: Users, section: 'Configuration' },
    { label: 'Application Categories', path: '/admin/categories', icon: Building2 },
    { label: 'Document Requirements', path: '/admin/requirements', icon: ListChecks },
    { label: 'Settings', path: '/admin/settings', icon: Settings },
  ],
}
