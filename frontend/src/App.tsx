import { Navigate, Route, Routes } from 'react-router-dom'
import { RoleProvider, useRole } from '@/app/RoleContext'
import { RequireRole } from '@/app/RequireRole'
import { ROLE_HOME } from '@/lib/nav'
import { OfficerDashboard } from '@/pages/officer/OfficerDashboard'
import { QueuePage } from '@/pages/officer/QueuePage'
import { ApplicationDetailPage } from '@/pages/officer/ApplicationDetailPage'
import { ComparisonPage } from '@/pages/officer/ComparisonPage'
import { ApplicantDashboard } from '@/pages/applicant/ApplicantDashboard'
import { ApplicantDetailPage } from '@/pages/applicant/ApplicantDetailPage'
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
import { HandbookPage } from '@/pages/admin/HandbookPage'
import { IntegrationsPage } from '@/pages/admin/IntegrationsPage'
import { SystemHealthPage } from '@/pages/admin/SystemHealthPage'
import { DelegationPage } from '@/pages/admin/DelegationPage'

function RoleHomeRedirect() {
  const { role } = useRole()
  return <Navigate to={ROLE_HOME[role]} replace />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RoleHomeRedirect />} />

      {/* Scrutiny Officer */}
      <Route element={<RequireRole role="officer" />}>
        <Route path="/officer" element={<OfficerDashboard />} />
        <Route path="/officer/queue" element={<QueuePage />} />
        <Route path="/officer/applications/:id" element={<ApplicationDetailPage />} />
        <Route path="/officer/comparison" element={<ComparisonPage />} />
        {/* Retired placeholder pages redirect to the queue (see LEGACY_REDIRECTS). */}
        <Route path="/officer/documents" element={<Navigate to="/officer/queue" replace />} />
        <Route path="/officer/extracted" element={<Navigate to="/officer/queue" replace />} />
        <Route path="/officer/findings" element={<Navigate to="/officer/queue" replace />} />
        <Route path="/officer/verification" element={<Navigate to="/officer/queue" replace />} />
        <Route path="/officer/decisions" element={<Navigate to="/officer/queue" replace />} />
        <Route path="/officer/reports" element={<Navigate to="/officer/queue" replace />} />
      </Route>

      {/* Applicant */}
      <Route element={<RequireRole role="applicant" />}>
        <Route path="/applicant" element={<ApplicantDashboard />} />
        <Route path="/applicant/applications" element={<ApplicantApplicationsPage />} />
        <Route path="/applicant/applications/new" element={<NewApplicationPage />} />
        <Route path="/applicant/applications/:id" element={<ApplicantDetailPage />} />
        <Route path="/applicant/uploads" element={<UploadPage />} />
        <Route path="/applicant/deficiencies" element={<DeficienciesPage />} />
        <Route path="/applicant/checklist" element={<Navigate to="/applicant/applications" replace />} />
        <Route path="/applicant/precheck" element={<Navigate to="/applicant/applications" replace />} />
        <Route path="/applicant/history" element={<Navigate to="/applicant/applications" replace />} />
      </Route>

      {/* Regional Officer */}
      <Route element={<RequireRole role="regional_officer" />}>
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/delegation" element={<DelegationPage />} />
        <Route path="/admin/users" element={<UsersPage />} />
        <Route path="/admin/categories" element={<CategoriesPage />} />
        <Route path="/admin/requirements" element={<RequirementsPage />} />
        <Route path="/admin/rules" element={<RulesPage />} />
        <Route path="/admin/handbook" element={<HandbookPage />} />
        <Route path="/admin/integrations" element={<IntegrationsPage />} />
        <Route path="/admin/audit" element={<AuditPage />} />
        <Route path="/admin/health" element={<SystemHealthPage />} />
        <Route path="/admin/settings" element={<SettingsPage />} />
      </Route>

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

