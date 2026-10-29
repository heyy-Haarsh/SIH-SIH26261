import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { RoleProvider, useRole } from '@/app/RoleContext'
import { RequireRole } from '@/app/RequireRole'
import { ROLE_HOME } from '@/lib/nav'
import { ToastProvider } from '@/components/ui/Toast'
import { PageSkeleton } from '@/components/ui/Skeleton'

// ── Lazy Loaded Pages for Code Splitting & Smooth Transitions ───────────────

// Scrutiny Officer
const OfficerDashboard = lazy(() =>
  import('@/pages/officer/OfficerDashboard').then((m) => ({ default: m.OfficerDashboard })),
)
const QueuePage = lazy(() =>
  import('@/pages/officer/QueuePage').then((m) => ({ default: m.QueuePage })),
)
const ApplicationDetailPage = lazy(() =>
  import('@/pages/officer/ApplicationDetailPage').then((m) => ({ default: m.ApplicationDetailPage })),
)
const CrossDocumentAnalysisPage = lazy(() =>
  import('@/pages/officer/ComparisonPage').then((m) => ({ default: m.CrossDocumentAnalysisPage })),
)
const OfficerClarificationsPage = lazy(() =>
  import('@/pages/officer/OfficerClarificationsPage').then((m) => ({ default: m.OfficerClarificationsPage })),
)
const CompletedReviewsPage = lazy(() =>
  import('@/pages/officer/CompletedReviewsPage').then((m) => ({ default: m.CompletedReviewsPage })),
)
const OfficerAuditPage = lazy(() =>
  import('@/pages/officer/OfficerAuditPage').then((m) => ({ default: m.OfficerAuditPage })),
)

// Applicant
const ApplicantDashboard = lazy(() =>
  import('@/pages/applicant/ApplicantDashboard').then((m) => ({ default: m.ApplicantDashboard })),
)
const ApplicantDetailPage = lazy(() =>
  import('@/pages/applicant/ApplicantDetailPage').then((m) => ({ default: m.ApplicantDetailPage })),
)
const ApplicantApplicationsPage = lazy(() =>
  import('@/pages/applicant/ApplicantApplicationsPage').then((m) => ({ default: m.ApplicantApplicationsPage })),
)
const NewApplicationPage = lazy(() =>
  import('@/pages/applicant/NewApplicationPage').then((m) => ({ default: m.NewApplicationPage })),
)
const UploadPage = lazy(() =>
  import('@/pages/applicant/UploadPage').then((m) => ({ default: m.UploadPage })),
)
const ClarificationsPage = lazy(() =>
  import('@/pages/applicant/ClarificationsPage').then((m) => ({ default: m.ClarificationsPage })),
)
const NotificationsPage = lazy(() =>
  import('@/pages/applicant/NotificationsPage').then((m) => ({ default: m.NotificationsPage })),
)

// Regional Officer / Admin
const AdminDashboard = lazy(() =>
  import('@/pages/admin/AdminDashboard').then((m) => ({ default: m.AdminDashboard })),
)
const RequirementsPage = lazy(() =>
  import('@/pages/admin/RequirementsPage').then((m) => ({ default: m.RequirementsPage })),
)
const UsersPage = lazy(() =>
  import('@/pages/admin/UsersPage').then((m) => ({ default: m.UsersPage })),
)
const CategoriesPage = lazy(() =>
  import('@/pages/admin/CategoriesPage').then((m) => ({ default: m.CategoriesPage })),
)
const CategoryDetailPage = lazy(() =>
  import('@/pages/admin/CategoryDetailPage').then((m) => ({ default: m.CategoryDetailPage })),
)
const RulesOverviewPage = lazy(() =>
  import('@/pages/admin/RulesOverviewPage').then((m) => ({ default: m.RulesOverviewPage })),
)
const RulesPage = lazy(() =>
  import('@/pages/admin/RulesPage').then((m) => ({ default: m.RulesPage })),
)
const AuditPage = lazy(() =>
  import('@/pages/admin/AuditPage').then((m) => ({ default: m.AuditPage })),
)
const SettingsPage = lazy(() =>
  import('@/pages/admin/SettingsPage').then((m) => ({ default: m.SettingsPage })),
)
const HandbookPage = lazy(() =>
  import('@/pages/admin/HandbookPage').then((m) => ({ default: m.HandbookPage })),
)
const IntegrationsPage = lazy(() =>
  import('@/pages/admin/IntegrationsPage').then((m) => ({ default: m.IntegrationsPage })),
)
const SystemHealthPage = lazy(() =>
  import('@/pages/admin/SystemHealthPage').then((m) => ({ default: m.SystemHealthPage })),
)
const DelegationPage = lazy(() =>
  import('@/pages/admin/DelegationPage').then((m) => ({ default: m.DelegationPage })),
)

function RoleHomeRedirect() {
  const { role } = useRole()
  return <Navigate to={ROLE_HOME[role]} replace />
}

function AppRoutes() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        <Route path="/" element={<RoleHomeRedirect />} />

        {/* Scrutiny Officer */}
        <Route element={<RequireRole role="officer" />}>
          <Route path="/officer" element={<OfficerDashboard />} />
          <Route path="/officer/queue" element={<QueuePage />} />
          <Route path="/officer/applications/:id" element={<ApplicationDetailPage />} />
          <Route path="/officer/clarifications" element={<OfficerClarificationsPage />} />
          <Route path="/officer/completed" element={<CompletedReviewsPage />} />
          <Route path="/officer/analysis" element={<CrossDocumentAnalysisPage />} />
          <Route path="/officer/audit" element={<OfficerAuditPage />} />
          {/* Legacy redirects */}
          <Route path="/officer/comparison" element={<Navigate to="/officer/analysis" replace />} />
          <Route path="/officer/documents" element={<Navigate to="/officer/queue" replace />} />
          <Route path="/officer/extracted" element={<Navigate to="/officer/queue" replace />} />
          <Route path="/officer/findings" element={<Navigate to="/officer/queue" replace />} />
          <Route path="/officer/verification" element={<Navigate to="/officer/queue" replace />} />
          <Route path="/officer/decisions" element={<Navigate to="/officer/completed" replace />} />
          <Route path="/officer/reports" element={<Navigate to="/officer/completed" replace />} />
        </Route>

        {/* Applicant */}
        <Route element={<RequireRole role="applicant" />}>
          <Route path="/applicant" element={<ApplicantDashboard />} />
          <Route path="/applicant/applications" element={<ApplicantApplicationsPage />} />
          <Route path="/applicant/applications/new" element={<NewApplicationPage />} />
          <Route path="/applicant/applications/:id" element={<ApplicantDetailPage />} />
          <Route path="/applicant/uploads" element={<UploadPage />} />
          <Route path="/applicant/clarifications" element={<ClarificationsPage />} />
          <Route path="/applicant/notifications" element={<NotificationsPage />} />
          <Route path="/applicant/uploads" element={<Navigate to="/applicant/applications" replace />} />
          <Route path="/applicant/deficiencies" element={<Navigate to="/applicant/clarifications" replace />} />
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
          <Route path="/admin/categories/:id" element={<CategoryDetailPage />} />
          <Route path="/admin/requirements" element={<Navigate to="/admin/categories" replace />} />
          <Route path="/admin/rules" element={<RulesOverviewPage />} />
          <Route path="/admin/rules/platform" element={<RulesPage />} />
          <Route path="/admin/integrations" element={<IntegrationsPage />} />
          <Route path="/admin/audit" element={<AuditPage />} />
          <Route path="/admin/health" element={<SystemHealthPage />} />
          <Route path="/admin/handbook" element={<HandbookPage />} />
          <Route path="/admin/settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <RoleProvider>
      <ToastProvider>
        <AppRoutes />
      </ToastProvider>
    </RoleProvider>
  )
}
