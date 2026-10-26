import { Navigate, Route, Routes } from 'react-router-dom'
import { RoleProvider, useRole } from '@/app/RoleContext'
import { ROLE_HOME } from '@/lib/nav'
import { OfficerDashboard } from '@/pages/officer/OfficerDashboard'
import { QueuePage } from '@/pages/officer/QueuePage'
import { ApplicationDetailPage } from '@/pages/officer/ApplicationDetailPage'
import { ApplicantDashboard } from '@/pages/applicant/ApplicantDashboard'
import { ApplicantApplicationsPage } from '@/pages/applicant/ApplicantApplicationsPage'
import { NewApplicationPage } from '@/pages/applicant/NewApplicationPage'
import { UploadPage } from '@/pages/applicant/UploadPage'
import { AdminDashboard } from '@/pages/admin/AdminDashboard'
import { PlaceholderPage } from '@/pages/shared/PlaceholderPage'
import {
  Activity,
  ClipboardCheck,
  FileSearch,
  FileText,
  GitCompare,
  HeartPulse,
  History,
  ListChecks,
  Plug,
  Scale,
  ScrollText,
  Settings,
  Shield,
  Users,
  Building2,
  AlertTriangle,
} from 'lucide-react'

function RoleHomeRedirect() {
  const { role } = useRole()
  return <Navigate to={ROLE_HOME[role]} replace />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RoleHomeRedirect />} />

      {/* Scrutiny Officer */}
      <Route path="/officer" element={<OfficerDashboard />} />
      <Route path="/officer/queue" element={<QueuePage />} />
      <Route path="/officer/applications/:id" element={<ApplicationDetailPage />} />
      <Route
        path="/officer/documents"
        element={
          <PlaceholderPage
            title="Document Viewer"
            breadcrumbs={['Scrutiny Officer', 'Documents']}
            description="Open an application from the queue to inspect uploaded documents and previews."
            icon={FileSearch}
          />
        }
      />
      <Route
        path="/officer/extracted"
        element={
          <PlaceholderPage
            title="Extracted Fields"
            breadcrumbs={['Scrutiny Officer', 'Extracted Fields']}
            description="Extracted fields with page references are available on each application details page."
            icon={ScrollText}
          />
        }
      />
      <Route
        path="/officer/findings"
        element={
          <PlaceholderPage
            title="Validation Findings"
            breadcrumbs={['Scrutiny Officer', 'Findings']}
            description="Aggregated findings browser will list cross-application results. Use application details for evidence today."
            icon={Shield}
          />
        }
      />
      <Route
        path="/officer/comparison"
        element={
          <PlaceholderPage
            title="Cross-document Comparison"
            breadcrumbs={['Scrutiny Officer', 'Comparison']}
            description="Discrepancy comparison is available inside application details under Cross-document."
            icon={GitCompare}
          />
        }
      />
      <Route
        path="/officer/verification"
        element={
          <PlaceholderPage
            title="External Verification"
            breadcrumbs={['Scrutiny Officer', 'Verification']}
            description="Verification statuses (including source unavailable / simulated) appear on application details."
            icon={Plug}
          />
        }
      />
      <Route
        path="/officer/decisions"
        element={
          <PlaceholderPage
            title="Review Decisions"
            breadcrumbs={['Scrutiny Officer', 'Decisions']}
            description="Decision recording UI will bind to review APIs. Notes and actions are sketched on application details."
            icon={ClipboardCheck}
          />
        }
      />
      <Route
        path="/officer/reports"
        element={
          <PlaceholderPage
            title="Scrutiny Reports"
            breadcrumbs={['Scrutiny Officer', 'Reports']}
            description="Report generation module is designed but not yet exporting PDF/DOCX packages."
            icon={FileText}
          />
        }
      />

      {/* Applicant */}
      <Route path="/applicant" element={<ApplicantDashboard />} />
      <Route path="/applicant/applications" element={<ApplicantApplicationsPage />} />
      <Route path="/applicant/applications/new" element={<NewApplicationPage />} />
      <Route path="/applicant/applications/:id" element={<ApplicationDetailPage />} />
      <Route path="/applicant/uploads" element={<UploadPage />} />
      <Route
        path="/applicant/checklist"
        element={
          <PlaceholderPage
            title="Document Checklist"
            breadcrumbs={['Applicant', 'Checklist']}
            description="Per-application checklists are shown on the application details page."
            icon={ListChecks}
          />
        }
      />
      <Route
        path="/applicant/precheck"
        element={
          <PlaceholderPage
            title="Pre-check Results"
            breadcrumbs={['Applicant', 'Pre-check']}
            description="Upload a document to trigger backend file checks and a validation run, then review findings."
            icon={ClipboardCheck}
          />
        }
      />
      <Route
        path="/applicant/deficiencies"
        element={
          <PlaceholderPage
            title="Deficiency Notices"
            breadcrumbs={['Applicant', 'Deficiencies']}
            description="Deficiency response workflow will list officer-issued notices. Demo findings appear on application details."
            icon={AlertTriangle}
          />
        }
      />
      <Route
        path="/applicant/history"
        element={
          <PlaceholderPage
            title="Application History"
            breadcrumbs={['Applicant', 'History']}
            description="Historical status transitions will appear here; audit events are visible on application details."
            icon={History}
          />
        }
      />

      {/* Administrator */}
      <Route path="/admin" element={<AdminDashboard />} />
      <Route
        path="/admin/users"
        element={
          <PlaceholderPage
            title="Users & Roles"
            breadcrumbs={['Administrator', 'Users']}
            description="User and role management APIs are scaffolded. Only applicant, officer, and admin roles exist."
            icon={Users}
          />
        }
      />
      <Route
        path="/admin/categories"
        element={
          <PlaceholderPage
            title="Application Categories"
            breadcrumbs={['Administrator', 'Categories']}
            description="Category configuration will drive document requirements per application type."
            icon={Building2}
          />
        }
      />
      <Route
        path="/admin/requirements"
        element={
          <PlaceholderPage
            title="Document Requirements"
            breadcrumbs={['Administrator', 'Requirements']}
            description="Versioned document requirement matrices will be managed here."
            icon={ListChecks}
          />
        }
      />
      <Route
        path="/admin/rules"
        element={
          <PlaceholderPage
            title="Regulatory Rules"
            breadcrumbs={['Administrator', 'Rules']}
            description="Versioned synthetic demo rules are seeded in the backend. Official handbook rules will replace them after verification."
            icon={Scale}
          />
        }
      />
      <Route
        path="/admin/integrations"
        element={
          <PlaceholderPage
            title="Integration Configuration"
            breadcrumbs={['Administrator', 'Integrations']}
            description="Configure MinIO, Redis/Celery, and authorized verification connectors. Nothing is presented as live without configuration."
            icon={Plug}
          />
        }
      />
      <Route
        path="/admin/audit"
        element={
          <PlaceholderPage
            title="Audit Trail"
            breadcrumbs={['Administrator', 'Audit']}
            description="System-wide audit browser will aggregate security-relevant events."
            icon={Activity}
          />
        }
      />
      <Route
        path="/admin/health"
        element={
          <PlaceholderPage
            title="System Health"
            breadcrumbs={['Administrator', 'Health']}
            description="See the System Overview dashboard for the live health probe and connector honesty panel."
            icon={HeartPulse}
          />
        }
      />
      <Route
        path="/admin/settings"
        element={
          <PlaceholderPage
            title="Settings"
            breadcrumbs={['Administrator', 'Settings']}
            description="Retention, upload limits, and environment flags will be managed here."
            icon={Settings}
          />
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <RoleProvider>
      <AppRoutes />
    </RoleProvider>
  )
}
