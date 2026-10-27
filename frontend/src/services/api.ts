import type {
  AdminAuditDetail,
  AdminAuditPage,
  AuditFacets,
  Integration,
  IntegrationList,
  RuleDraftProposal,
  RuleImportResult,
  RuleImportValidation,
  RuleUsage,
  SystemHealth,
  AdminCategory,
  AdminInstitution,
  AdminRule,
  AdminSetting,
  AdminStats,
  AdminUser,
  ApiHealth,
  ApplicantApplication,
  ApplicantApplicationSummary,
  ApplicationDetail,
  ApplicationMetrics,
  ApplicationSummary,
  DeficiencyNotice,
  DocumentCheck,
  UploadPolicy,
  Discrepancy,
  DocumentVerificationCheck,
  DocumentVerificationRun,
  DocumentReport,
  ExtractionRun,
  Finding,
  ForensicsIndicator,
  ForensicsRun,
  HandbookReferenceAdmin,
  ReconciliationRun,
  ScrutinyReview,
} from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export class ApiError extends Error {
  status: number
  /** Machine-readable server code, e.g. `open_clarifications`, `file_too_large`. */
  code?: string
  constructor(status: number, message: string, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

function formatDetail(body: unknown): string {
  if (!body || typeof body !== 'object') return String(body ?? '')
  const detail = (body as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') {
    const d = detail as { message?: string; code?: string }
    if (d.message) return d.code ? `${d.code}: ${d.message}` : d.message
    return JSON.stringify(detail)
  }
  return JSON.stringify(body)
}

async function request<T>(
  path: string,
  options: RequestInit & { role?: string } = {},
): Promise<T> {
  const { role, headers, ...rest } = options
  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      ...(role ? { 'X-Demo-Role': role, 'X-Demo-User-Id': `demo-${role}` } : {}),
      ...headers,
    },
  })
  if (!res.ok) {
    let detail = res.statusText
    let code: string | undefined
    try {
      const body = await res.json()
      detail = formatDetail(body) || res.statusText
      if (body && typeof body === 'object' && typeof (body as { code?: unknown }).code === 'string') {
        code = (body as { code: string }).code
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail, code)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export interface AuditSearchParams {
  action?: string
  category?: string
  actor?: string
  actorRole?: string
  applicationNumber?: string
  entityType?: string
  q?: string
  dateFrom?: string
  dateTo?: string
  limit?: number
  offset?: number
}

function auditQuery(params: AuditSearchParams): string {
  const q = new URLSearchParams()
  const map: Array<[keyof AuditSearchParams, string]> = [
    ['action', 'action'],
    ['category', 'category'],
    ['actor', 'actor'],
    ['actorRole', 'actor_role'],
    ['applicationNumber', 'application_number'],
    ['entityType', 'entity_type'],
    ['q', 'q'],
    ['dateFrom', 'date_from'],
    ['dateTo', 'date_to'],
  ]
  for (const [key, name] of map) {
    const value = params[key]
    if (value) q.set(name, String(value))
  }
  if (params.limit != null) q.set('limit', String(params.limit))
  if (params.offset != null) q.set('offset', String(params.offset))
  const qs = q.toString()
  return qs ? `?${qs}` : ''
}
async function requestBlob(path: string, role: string): Promise<{ blob: Blob; fileName?: string }> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'X-Demo-Role': role, 'X-Demo-User-Id': `demo-${role}` },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = formatDetail(await res.json()) || res.statusText
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail)
  }
  const disposition = res.headers.get('content-disposition') ?? ''
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition)
  return { blob: await res.blob(), fileName: match ? decodeURIComponent(match[1]) : undefined }
}

export interface UploadDocumentResult {
  documentId: string
  validationRunId: string | null
  extractionRunId: string | null
  extractionStatus: string | null
  findings: unknown[]
  fileChecks: unknown
  pipelineOk?: boolean
  pipelineWarnings?: string[]
  documentCheck?: DocumentCheck | null
  documentVersion?: number | null
  replacedPrevious?: boolean
}

export const api = {
  health: () => request<ApiHealth>('/health'),

  listApplications: (role: string) =>
    request<ApplicationSummary[]>('/applications', { role }),

  applicationMetrics: (role: string) =>
    request<ApplicationMetrics>('/applications/metrics', { role }),

  getApplication: (id: string, role: string) =>
    request<ApplicationDetail>(`/applications/${id}`, { role }),

  // ---- Applicant-only views (narrow DTOs: no internal scrutiny data) ----
  listMyApplications: (role: string) =>
    request<ApplicantApplicationSummary[]>('/applicant/applications', { role }),

  getMyApplication: (id: string, role: string) =>
    request<ApplicantApplication>(`/applicant/applications/${id}`, { role }),

  uploadPolicy: (role: string) => request<UploadPolicy>('/applications/upload-policy', { role }),

  createApplication: (
    role: string,
    body: {
      category_code: string
      institution_name: string
      program_name: string
      academic_year: string
    },
  ) =>
    request<ApplicantApplication>('/applications', {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  uploadDocument: (role: string, applicationId: string, file: File, requirementCode: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('requirement_code', requirementCode)
    return request<UploadDocumentResult>(`/applications/${applicationId}/documents`, {
      method: 'POST',
      role,
      body: form,
    })
  },

  runValidation: (role: string, applicationId: string) =>
    request<{ validationRunId: string; findings: unknown[]; status: string }>(
      `/applications/${applicationId}/validation-runs`,
      { method: 'POST', role },
    ),

  startExtraction: (role: string, documentId: string, force = false) =>
    request<ExtractionRun>(`/documents/${documentId}/extraction-runs`, {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force, run_validation_after: true }),
    }),

  latestExtraction: (role: string, documentId: string) =>
    request<ExtractionRun | null>(`/documents/${documentId}/extraction-runs/latest`, { role }),

  getExtractionRun: (role: string, runId: string) =>
    request<ExtractionRun>(`/extraction-runs/${runId}`, { role }),

  ocrCapability: (role: string) =>
    request<{
      enabled: boolean
      available: boolean
      message: string
      languagesMissing: string[]
      languagesUsable: string[]
      marathiSupported: boolean
    }>('/extraction/ocr-capability', { role }),

  runReconciliation: (role: string, applicationId: string) =>
    request<ReconciliationRun>(`/applications/${applicationId}/reconciliation-runs`, {
      method: 'POST',
      role,
    }),

  latestReconciliation: (role: string, applicationId: string) =>
    request<ReconciliationRun | null>(
      `/applications/${applicationId}/reconciliation-runs/latest`,
      { role },
    ),

  listReconciliationItems: (role: string, applicationId: string) =>
    request<Discrepancy[]>(`/applications/${applicationId}/reconciliation-items`, { role }),

  resolveReconciliationItem: (
    role: string,
    itemId: string,
    body: { status: string; reason: string },
  ) =>
    request<Discrepancy>(`/reconciliation-items/${itemId}/resolve`, {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  runForensics: (role: string, applicationId: string) =>
    request<ForensicsRun>(`/applications/${applicationId}/forensics-runs`, {
      method: 'POST',
      role,
    }),

  latestForensics: (role: string, applicationId: string) =>
    request<ForensicsRun | null>(`/applications/${applicationId}/forensics-runs/latest`, { role }),

  listForensicsIndicators: (role: string, applicationId: string) =>
    request<ForensicsIndicator[]>(`/applications/${applicationId}/forensics-indicators`, { role }),

  resolveForensicsIndicator: (
    role: string,
    indicatorId: string,
    body: { status: string; reason: string },
  ) =>
    request<ForensicsIndicator>(`/forensics-indicators/${indicatorId}/resolve`, {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  startScrutiny: (role: string, applicationId: string) =>
    request<ApplicationDetail>(`/applications/${applicationId}/scrutiny/start`, {
      method: 'POST',
      role,
    }),

  requestClarification: (
    role: string,
    applicationId: string,
    body: { title: string; description: string; finding_ids?: string[] },
  ) =>
    request<ApplicationDetail>(`/applications/${applicationId}/scrutiny/clarification`, {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  recordDecision: (
    role: string,
    applicationId: string,
    body: { reason: string; recommend: boolean },
  ) =>
    request<ApplicationDetail>(`/applications/${applicationId}/scrutiny/decision`, {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  addReviewNote: (role: string, applicationId: string, content: string) =>
    request<ApplicationDetail>(`/applications/${applicationId}/scrutiny/notes`, {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    }),

  resubmitApplication: (role: string, applicationId: string, note = '') =>
    request<ApplicantApplication>(`/applications/${applicationId}/resubmit`, {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    }),

  refreshScrutinySummary: (role: string, applicationId: string) =>
    request<ApplicationDetail>(`/applications/${applicationId}/scrutiny/refresh-summary`, {
      method: 'POST',
      role,
    }),

  listDeficiencies: (role: string, applicationId?: string) =>
    request<DeficiencyNotice[]>(
      applicationId ? `/applications/${applicationId}/deficiencies` : '/deficiencies',
      { role },
    ),

  respondDeficiency: (role: string, deficiencyId: string, response: string) =>
    request<DeficiencyNotice>(`/deficiencies/${deficiencyId}/respond`, {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response }),
    }),

  resolveFinding: (role: string, findingId: string, body: { status: string; reason: string }) =>
    request<Finding>(`/findings/${findingId}/resolve`, {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  // ---- Admin (Phase 6) ----------------------------------------------------
  adminStats: (role: string) => request<AdminStats>('/admin/stats', { role }),

  listAdminUsers: (role: string) => request<AdminUser[]>('/admin/users', { role }),

  listInstitutions: (role: string) =>
    request<AdminInstitution[]>('/admin/institutions', { role }),

  createAdminUser: (
    role: string,
    body: {
      name: string
      email: string
      role: string
      institution_id?: string | null
      is_active?: boolean
    },
  ) =>
    request<AdminUser>('/admin/users', {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateAdminUser: (
    role: string,
    userId: string,
    body: Record<string, unknown>,
  ) =>
    request<AdminUser>(`/admin/users/${userId}`, {
      method: 'PATCH',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  deactivateAdminUser: (role: string, userId: string, reason: string) =>
    request<AdminUser>(
      `/admin/users/${userId}/deactivate?reason=${encodeURIComponent(reason)}`,
      { method: 'POST', role },
    ),

  listCategories: (role: string, onlyActive = false) =>
    request<AdminCategory[]>(`/admin/categories?only_active=${onlyActive}`, { role }),

  createCategory: (role: string, body: Record<string, unknown>) =>
    request<AdminCategory>('/admin/categories', {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateCategory: (role: string, categoryId: string, body: Record<string, unknown>) =>
    request<AdminCategory>(`/admin/categories/${categoryId}`, {
      method: 'PATCH',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  listAdminRules: (role: string, opts?: { onlyActive?: boolean; synthetic?: boolean }) => {
    const q = new URLSearchParams()
    if (opts?.onlyActive) q.set('only_active', 'true')
    if (opts?.synthetic !== undefined) q.set('synthetic', String(opts.synthetic))
    const qs = q.toString()
    return request<AdminRule[]>(`/admin/rules${qs ? `?${qs}` : ''}`, { role })
  },

  createAdminRule: (role: string, body: Record<string, unknown>) =>
    request<AdminRule>('/admin/rules', {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateAdminRule: (role: string, ruleId: string, body: Record<string, unknown>) =>
    request<AdminRule>(`/admin/rules/${ruleId}`, {
      method: 'PATCH',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  createRuleVersion: (role: string, ruleId: string, body: Record<string, unknown>) =>
    request<AdminRule>(`/admin/rules/${ruleId}/versions`, {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  publishRuleVersion: (role: string, ruleId: string, version: string, reason = '') =>
    request<AdminRule>(
      `/admin/rules/${ruleId}/versions/${encodeURIComponent(version)}/publish?reason=${encodeURIComponent(reason)}`,
      { method: 'POST', role },
    ),

  reactivateRuleVersion: (role: string, ruleId: string, version: string, reason: string) =>
    request<AdminRule>(
      `/admin/rules/${ruleId}/versions/${encodeURIComponent(version)}/reactivate?reason=${encodeURIComponent(reason)}`,
      { method: 'POST', role },
    ),

  validateAdminRule: (role: string, body: Record<string, unknown>) =>
    request<{ valid: boolean; errors: string[]; warnings: string[] }>('/admin/rules/validate', {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  listAdminSettings: (role: string) => request<AdminSetting[]>('/admin/settings', { role }),

  updateAdminSetting: (
    role: string,
    key: string,
    body: { value: Record<string, unknown>; change_reason: string },
  ) =>
    request<AdminSetting>(`/admin/settings/${encodeURIComponent(key)}`, {
      method: 'PUT',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  searchAudit: (role: string, params: AuditSearchParams = {}) =>
    request<AdminAuditPage>(`/admin/audit${auditQuery(params)}`, { role }),

  auditFacets: (role: string) => request<AuditFacets>('/admin/audit/facets', { role }),

  getAuditEvent: (role: string, id: string) =>
    request<AdminAuditDetail>(`/admin/audit/${encodeURIComponent(id)}`, { role }),

  exportAuditCsv: (role: string, params: AuditSearchParams = {}) =>
    requestBlob(`/admin/audit/export.csv${auditQuery({ ...params, limit: undefined, offset: undefined })}`, role),

  verifyAuditChain: (role: string) =>
    request<{ ok: boolean; checked: number; firstBadSequence: number | null; detail: string }>(
      '/admin/audit-chain/verify',
      { role },
    ),

  // ---- Integrations & system health (admin) ----------------------------------
  listIntegrations: (role: string) => request<IntegrationList>('/admin/integrations', { role }),

  setIntegrationEnabled: (role: string, id: string, enabled: boolean, reason: string) =>
    request<Integration>(`/admin/integrations/${encodeURIComponent(id)}`, {
      method: 'PUT',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled, reason }),
    }),

  checkIntegration: (role: string, id: string) =>
    request<Integration>(`/admin/integrations/${encodeURIComponent(id)}/check`, {
      method: 'POST',
      role,
    }),

  systemHealth: (role: string) => request<SystemHealth>('/admin/system-health', { role }),

  // ---- Rule import, drafts, usage (admin) ------------------------------------
  validateRuleImport: (role: string, jsonText: string) =>
    request<RuleImportValidation>('/admin/rules/import/validate', {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ json_text: jsonText }),
    }),

  importRules: (role: string, jsonText: string) =>
    request<RuleImportResult>('/admin/rules/import', {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ json_text: jsonText }),
    }),

  draftRuleFromText: (role: string, text: string) =>
    request<RuleDraftProposal>('/admin/rules/draft-from-text', {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),

  saveRuleDraft: (role: string, rules: Array<Record<string, unknown>>) =>
    request<RuleImportResult>('/admin/rules/drafts', {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules }),
    }),

  discardRuleDraft: (role: string, ruleId: string, version: string, reason: string) =>
    request<AdminRule>(
      `/admin/rules/${ruleId}/versions/${encodeURIComponent(version)}/discard?reason=${encodeURIComponent(reason)}`,
      { method: 'POST', role },
    ),

  getRuleUsage: (role: string, ruleId: string) =>
    request<RuleUsage>(`/admin/rules/${ruleId}/usage`, { role }),
  // ---- Phase 7 document verification ------------------------------------
  listDocVerificationConfigs: (role: string) =>
    request<
      Array<{
        code: string
        requirementCode: string
        name: string
        version: string
        isSyntheticRules: boolean
        handbookNote?: string
        adapters: string[]
      }>
    >('/document-verification/configs', { role }),

  runApplicationDocVerification: (role: string, applicationId: string) =>
    request<DocumentVerificationRun[]>(`/applications/${applicationId}/document-verification`, {
      method: 'POST',
      role,
    }),

  listApplicationDocVerification: (role: string, applicationId: string) =>
    request<DocumentVerificationRun[]>(`/applications/${applicationId}/document-verification`, {
      role,
    }),

  resolveDocVerificationCheck: (
    role: string,
    checkId: string,
    body: { status: string; reason: string },
  ) =>
    request<DocumentVerificationCheck>(`/document-verification-checks/${checkId}/resolve`, {
      method: 'POST',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  // ---- Scrutiny review (officer/admin) -------------------------------------
  getScrutinyReview: (role: string, applicationId: string) =>
    request<ScrutinyReview>(`/applications/${applicationId}/scrutiny-review`, { role }),

  getDocumentReport: (role: string, applicationId: string, documentId: string) =>
    request<DocumentReport>(`/applications/${applicationId}/documents/${documentId}/report`, {
      role,
    }),

  /** Stored file as a Blob (the endpoint needs auth headers, so an <iframe src> cannot be used). */
  fetchDocumentFile: (role: string, documentId: string) =>
    requestBlob(`/documents/${documentId}/file`, role),

  downloadScrutinyPdf: (role: string, applicationId: string) =>
    requestBlob(`/applications/${applicationId}/report.pdf`, role),

  // ---- Handbook references (admin) -----------------------------------------
  listHandbookReferences: (role: string) =>
    request<HandbookReferenceAdmin[]>('/admin/handbook-references', { role }),

  saveHandbookReference: (
    role: string,
    body: {
      reference_key: string
      edition: string
      section: string
      page: string
      title: string
      source_note: string
      academic_year?: string
      applicable_categories?: string
      verified: boolean
    },
  ) =>
    request<HandbookReferenceAdmin>('/admin/handbook-references', {
      method: 'PUT',
      role,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  deleteHandbookReference: (role: string, id: string) =>
    request<{ ok: boolean }>(`/admin/handbook-references/${id}`, { method: 'DELETE', role }),
}
