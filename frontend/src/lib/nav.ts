import {
  Activity,
  AlertTriangle,
  Building2,
  ClipboardCheck,
  FileSearch,
  FileText,
  FolderOpen,
  GitCompare,
  HeartPulse,
  History,
  LayoutDashboard,
  ListChecks,
  Plug,
  Scale,
  ScrollText,
  Settings,
  Shield,
  Upload,
  Users,
  type LucideIcon,
} from 'lucide-react'
import type { UserRole } from '@/types'

export interface NavItem {
  label: string
  path: string
  icon: LucideIcon
}

export const ROLE_HOME: Record<UserRole, string> = {
  applicant: '/applicant',
  officer: '/officer',
  admin: '/admin',
}

export const NAV_BY_ROLE: Record<UserRole, NavItem[]> = {
  applicant: [
    { label: 'Dashboard', path: '/applicant', icon: LayoutDashboard },
    { label: 'My Applications', path: '/applicant/applications', icon: FolderOpen },
    { label: 'New Application', path: '/applicant/applications/new', icon: FileText },
    { label: 'Document Checklist', path: '/applicant/checklist', icon: ListChecks },
    { label: 'Document Uploads', path: '/applicant/uploads', icon: Upload },
    { label: 'Pre-check Results', path: '/applicant/precheck', icon: ClipboardCheck },
    { label: 'Deficiency Notices', path: '/applicant/deficiencies', icon: AlertTriangle },
    { label: 'Application History', path: '/applicant/history', icon: History },
  ],
  officer: [
    { label: 'Overview', path: '/officer', icon: LayoutDashboard },
    { label: 'Application Queue', path: '/officer/queue', icon: FolderOpen },
    { label: 'Document Viewer', path: '/officer/documents', icon: FileSearch },
    { label: 'Extracted Fields', path: '/officer/extracted', icon: ScrollText },
    { label: 'Validation Findings', path: '/officer/findings', icon: Shield },
    { label: 'Cross-doc Comparison', path: '/officer/comparison', icon: GitCompare },
    { label: 'External Verification', path: '/officer/verification', icon: Plug },
    { label: 'Review Decisions', path: '/officer/decisions', icon: ClipboardCheck },
    { label: 'Scrutiny Reports', path: '/officer/reports', icon: FileText },
  ],
  admin: [
    { label: 'System Overview', path: '/admin', icon: LayoutDashboard },
    { label: 'Users & Roles', path: '/admin/users', icon: Users },
    { label: 'App Categories', path: '/admin/categories', icon: Building2 },
    { label: 'Document Requirements', path: '/admin/requirements', icon: ListChecks },
    { label: 'Regulatory Rules', path: '/admin/rules', icon: Scale },
    { label: 'Integrations', path: '/admin/integrations', icon: Plug },
    { label: 'Audit Trail', path: '/admin/audit', icon: Activity },
    { label: 'System Health', path: '/admin/health', icon: HeartPulse },
    { label: 'Settings', path: '/admin/settings', icon: Settings },
  ],
}
