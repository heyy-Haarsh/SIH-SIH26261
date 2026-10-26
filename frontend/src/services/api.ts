import type {
  ApiHealth,
  ApplicationDetail,
  ApplicationSummary,
  DeficiencyNotice,
  Discrepancy,
  ExtractionRun,
  Finding,
  ForensicsIndicator,
  ForensicsRun,
  ReconciliationRun,
} from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
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
    try {
      const body = await res.json()
      detail = formatDetail(body) || res.statusText
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export interface UploadDocumentResult {
  documentId: string
  validationRunId: string | null
  extractionRunId: string | null
  extractionStatus: string | null
  findings: unknown[]
  fileChecks: unknown
}

export const api = {
  health: () => request<ApiHealth>('/health'),

  listApplications: (role: string) =>
    request<ApplicationSummary[]>('/applications', { role }),

  getApplication: (id: string, role: string) =>
    request<ApplicationDetail>(`/applications/${id}`, { role }),

  createApplication: (
    role: string,
    body: { category_code: string; program_name: string; academic_year: string },
  ) =>
    request<ApplicationSummary>('/applications', {
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
    request<ApplicationDetail>(`/applications/${applicationId}/resubmit`, {
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
}
