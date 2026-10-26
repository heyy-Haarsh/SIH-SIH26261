import { Navigate, Route, Routes } from 'react-router-dom'
import { RoleProvider, useRole } from '@/app/RoleContext'
import { ROLE_HOME } from '@/lib/nav'
import { OfficerDashboard } from '@/pages/officer/OfficerDashboard'
import { QueuePage } from '@/pages/officer/QueuePage'
import { ApplicationDetailPage } from '@/pages/officer/ApplicationDetailPage'
import { ComparisonPage } from '@/pages/officer/ComparisonPage'
import { ApplicantDashboard } from '@/pages/applicant/ApplicantDashboard'
import { ApplicantApplicationsPage } from '@/pages/applicant/ApplicantApplicationsPage'
import { NewApplicationPage } from '@/pages/applicant/NewApplicationPage'
import { UploadPage } from '@/pages/applicant/UploadPage'
import { DeficienciesPage } from '@/pages/applicant/DeficienciesPage'
import { AdminDashboard } from '@/pages/admin/AdminDashboard'
import { UsersPage } from '@/pages/admin/UsersPage'
import { CategoriesPage } from '@/pages/admin/CategoriesPage'
import { RequirementsPage } from '@/pages/admin/RequirementsPage'
import { RulesPage } from '@/pages/admin/RulesPage'
import { AuditPage } from '@/pages/admin/AuditPage'
import { SettingsPage } from '@/pages/admin/SettingsPage'
import { PlaceholderPage } from '@/pages/shared/PlaceholderPage'
import {
  ClipboardCheck,
  FileSearch,
  FileText,
  HeartPulse,
  History,
  ListChecks,
  Plug,
  ScrollText,
  Shield,
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
      <Route path="/officer/comparison" element={<ComparisonPage />} />
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
      <Route path="/applicant/deficiencies" element={<DeficienciesPage />} />
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
      <Route path="/admin/users" element={<UsersPage />} />
      <Route path="/admin/categories" element={<CategoriesPage />} />
      <Route path="/admin/requirements" element={<RequirementsPage />} />
      <Route path="/admin/rules" element={<RulesPage />} />
      <Route
        path="/admin/integrations"
        element={
          <PlaceholderPage
            title="Integration Configuration"
            breadcrumbs={['Administrator', 'Integrations']}
            description="Configure MinIO, Redis/Celery, and authorized verification connectors. Nothing is presented as live without configuration. Use Settings for verification toggles."
            icon={Plug}
          />
        }
      />
      <Route path="/admin/audit" element={<AuditPage />} />
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
      <Route path="/admin/settings" element={<SettingsPage />} />

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
