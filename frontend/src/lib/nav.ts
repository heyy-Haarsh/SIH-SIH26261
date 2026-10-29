import {
  Activity,
  Bell,
  MessagesSquare,
  BookOpen,
  Building2,
  CheckCircle2,
  FolderOpen,
  GitCompare,
  HeartPulse,
  LayoutDashboard,
  ListChecks,
  Plug,
  FilePlus2,
  Scale,
  Settings,
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
    { label: 'Overview', path: '/applicant', icon: LayoutDashboard },
    { label: 'Applications', path: '/applicant/applications', icon: FolderOpen },
    { label: 'Create Application', path: '/applicant/applications/new', icon: FilePlus2 },
    {
      label: 'Clarifications',
      path: '/applicant/clarifications',
      icon: MessagesSquare,
      badgeKey: 'clarifications',
    },
    { label: 'Notifications', path: '/applicant/notifications', icon: Bell, badgeKey: 'notifications' },
  ],
  officer: [
    { label: 'Overview', path: '/officer', icon: LayoutDashboard, section: 'Work' },
    {
      label: 'Review Queue',
      path: '/officer/queue',
      icon: ListChecks,
      badgeKey: 'myQueue',
    },
    {
      label: 'Clarifications',
      path: '/officer/clarifications',
      icon: MessagesSquare,
      badgeKey: 'openClarifications',
    },
    { label: 'Completed Reviews', path: '/officer/completed', icon: CheckCircle2 },
    {
      label: 'Cross-Document',
      path: '/officer/analysis',
      icon: GitCompare,
      section: 'Analysis',
    },
    { label: 'Audit Trail', path: '/officer/audit', icon: Activity },
  ],
  regional_officer: [
    { label: 'Overview', path: '/admin', icon: LayoutDashboard },
    { label: 'Application Categories', path: '/admin/categories', icon: Building2 },
    { label: 'Rules & Validation', path: '/admin/rules', icon: Scale },
    { label: 'Verification Sources', path: '/admin/integrations', icon: Plug },
    { label: 'Audit Logs', path: '/admin/audit', icon: Activity },
    { label: 'System Settings', path: '/admin/settings', icon: Settings },
    {
      label: 'Delegation Queue',
      path: '/admin/delegation',
      icon: Workflow,
      badgeKey: 'unassigned',
      section: 'Operations',
    },
    { label: 'System Health', path: '/admin/health', icon: HeartPulse },
    { label: 'Users & Roles', path: '/admin/users', icon: Users },
    { label: 'Handbook References', path: '/admin/handbook', icon: BookOpen },
  ],
}
