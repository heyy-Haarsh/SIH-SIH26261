export type UserRole = 'applicant' | 'officer' | 'admin'

export type ApplicationStatus =
  | 'draft'
  | 'submitted'
  | 'processing'
  | 'under_scrutiny'
  | 'clarification_required'
  | 'resubmitted'
  | 'recommended'
  | 'rejected'
  // Legacy statuses still returned by older rows
  | 'awaiting_review'
  | 'under_review'
  | 'deficiency'
  | 'manual_review'
  | 'approved'

export type FindingSeverity = 'info' | 'warning' | 'failed' | 'manual_review'
export type FindingStatus = 'open' | 'resolved' | 'waived' | 'accepted'
export type ValidationOutcome =
  | 'pass'
  | 'warning'
  | 'failed'
  | 'pending'
  | 'manual_review'
  | 'verification_unavailable'

export type VerificationSource =
  | 'authorized_live'
  | 'local_validation'
  | 'simulated_dev'
  | 'manual_reviewer'

export type VerificationStatus =
  | 'verified_by_source'
  | 'mismatch_detected'
  | 'expired'
  | 'verification_pending'
  | 'source_unavailable'
  | 'manual_review_required'
  | 'simulated_result'

export type Priority = 'low' | 'medium' | 'high' | 'critical'

export interface User {
  id: string
  name: string
  email: string
  role: UserRole
  institutionId?: string
  institutionName?: string
}

export interface Institution {
  id: string
  name: string
  code: string
  state: string
  type: string
}

export interface ApplicationSummary {
  id: string
  applicationNumber: string
  institutionId: string
  institutionName: string
  category: string
  categoryCode: string
  submittedAt: string | null
  status: ApplicationStatus
  priority: Priority
  deficiencyCount: number
  findingCount: number
  requiresManualReview: boolean
  /** Prioritization aid only — not proof of fraud or an automatic rejection */
  priorityScore?: number
  scoreConfigVersion?: string | null
  assignedOfficer?: string
}

export interface DeficiencyNotice {
  id: string
  applicationId: string
  applicationNumber?: string | null
  title: string
  description: string
  status: 'open' | 'responded' | 'closed'
  findingId?: string | null
  applicantResponse?: string | null
  respondedAt?: string | null
  createdAt: string
  resolvedAt?: string | null
}

export interface ScoreContribution {
  source: string
  label: string
  weightKey: string
  points: number
  refId?: string | null
  detail?: string
}

export interface DocumentRequirement {
  id: string
  code: string
  name: string
  mandatory: boolean
  status: 'missing' | 'uploaded' | 'replaced' | 'rejected'
  allowedTypes: string[]
}

export interface DocumentItem {
  id: string
  name: string
  requirementCode: string
  fileName: string
  mimeType: string
  sizeBytes: number
  uploadedAt: string
  version: number
  status: ValidationOutcome
  pageCount?: number
  extractionStatus?: string | null
  contentKind?: string | null
  predictedCategory?: string | null
  selectedCategory?: string | null
  categoryMismatch?: boolean
  latestExtractionRunId?: string | null
  /** Phase 7 — independent of authenticity */
  ruleValidationStatus?: string | null
  externalVerificationStatus?: string | null
  reviewStatus?: string | null
  latestVerificationRunId?: string | null
}

export interface DocumentVerificationCheck {
  id: string
  runId: string
  applicationId: string
  documentId: string
  layer: string
  checkCode: string
  title: string
  detail: string
  outcome: string
  severity: string
  source: string
  adapter: string
  isSyntheticRule: boolean
  evidence: Record<string, unknown>
  limitations: string[]
  status: string
  resolutionReason?: string | null
  resolvedAt?: string | null
  createdAt: string
}

export interface DocumentVerificationRun {
  id: string
  applicationId: string
  documentId: string
  documentVersionId: string
  configCode: string
  configVersion: string
  status: string
  ruleValidationStatus: string
  externalVerificationStatus: string
  reviewStatus: string
  summary: Record<string, unknown>
  limitations: string[]
  scrutinyReport: Record<string, unknown>
  createdAt: string
  completedAt?: string | null
  checks: DocumentVerificationCheck[]
}

export interface ExtractedField {
  id: string
  fieldName: string
  value: string
  rawValue?: string | null
  normalizedValue?: string | null
  confidence: number | null
  ocrConfidence?: number | null
  pageNumber?: number | null
  pageReference: string | null
  bbox?: { x0: number; y0: number; x1: number; y1: number } | null
  coordinateSpace?: string | null
  method?: string | null
  reviewStatus?: string | null
  isConflict?: boolean
  candidateValues?: unknown[]
  unit?: string | null
  sourceDocumentId: string
  sourceDocumentName: string
  extractionRunId?: string | null
  correctedValue?: string
}

export interface ExtractionRun {
  id: string
  documentVersionId: string
  applicationId: string
  validationRunId?: string | null
  status: string
  contentKind: string
  selectedCategory?: string | null
  predictedCategory: string
  categoryConfidence?: number | null
  categoryMethod?: string
  categoryMismatch: boolean
  warnings: string[]
  errorCode?: string | null
  errorMessage?: string | null
  ocrAvailable: boolean
  pageCount?: number | null
  pagesWithText: number
  pagesOcr: number
  fields: ExtractedField[]
}

export interface FindingEvidence {
  id: string
  description: string
  documentId?: string
  documentName?: string
  pageReference?: string
  ruleId?: string
  ruleVersion?: string
}

export interface Finding {
  id: string
  title: string
  description: string
  severity: FindingSeverity
  status: FindingStatus
  outcome: ValidationOutcome
  ruleId?: string
  ruleName?: string
  ruleVersion?: string
  handbookRef?: string
  evidence: FindingEvidence[]
  createdAt: string
}

export type ReconciliationOutcome =
  | 'MATCH'
  | 'MISMATCH'
  | 'MISSING_DATA'
  | 'POSSIBLE_DUPLICATE'
  | 'MANUAL_REVIEW'

export interface ReconciliationValue {
  documentId: string
  documentName: string
  value: string
  normalizedValue?: string | null
  page?: string | null
  pageNumber?: number | null
  extractedFieldId?: string | null
  evidenceSnippet?: string | null
}

export interface Discrepancy {
  id: string
  fieldName: string
  outcome: ReconciliationOutcome
  values: ReconciliationValue[]
  severity: FindingSeverity
  status: FindingStatus | 'cleared'
  title?: string | null
  description?: string | null
  matchKind?: string | null
  originalOutcome?: ReconciliationOutcome | null
  resolutionReason?: string | null
  resolvedAt?: string | null
  fingerprint?: string | null
}

export interface ReconciliationRun {
  id: string
  applicationId: string
  validationRunId?: string | null
  status: string
  trigger: string
  engineVersion: string
  inputFingerprint: string
  summary: Record<string, unknown>
  items: Discrepancy[]
  createdAt: string
  completedAt?: string | null
}

export interface VerificationResult {
  id: string
  claim: string
  status: VerificationStatus
  source: VerificationSource
  detail: string
  checkedAt: string | null
}

export type ForensicsRiskClass =
  | 'informational'
  | 'check_limitation'
  | 'technical_anomaly'
  | 'authenticity_concern'
  | 'possible_duplicate'

export interface ForensicsEvidence {
  id: string
  description: string
  documentId?: string | null
  documentName?: string | null
  pageNumber?: number | null
  pageReference?: string | null
  detail?: string | null
}

export interface ForensicsIndicator {
  id: string
  documentId?: string | null
  code: string
  riskClass: ForensicsRiskClass
  originalRiskClass?: ForensicsRiskClass | null
  severity: FindingSeverity
  status: FindingStatus | 'cleared'
  verificationStatus: VerificationStatus
  title: string
  description: string
  affectedPages: number[]
  evidence: ForensicsEvidence[]
  metadata?: Record<string, unknown>
  resolutionReason?: string | null
  resolvedAt?: string | null
  fingerprint?: string | null
}

export interface ForensicsRun {
  id: string
  applicationId: string
  validationRunId?: string | null
  status: string
  trigger: string
  engineVersion: string
  inputFingerprint: string
  summary: Record<string, unknown>
  limitations: string[]
  indicators: ForensicsIndicator[]
  createdAt: string
  completedAt?: string | null
}

export interface ReviewNote {
  id: string
  author: string
  role: UserRole
  content: string
  createdAt: string
}

export interface AuditEvent {
  id: string
  action: string
  actor: string
  timestamp: string
  detail: string
}

export interface ApplicationDetail extends ApplicationSummary {
  academicYear: string
  programName: string
  contactEmail: string
  requirements: DocumentRequirement[]
  documents: DocumentItem[]
  extractedFields: ExtractedField[]
  findings: Finding[]
  discrepancies: Discrepancy[]
  forensicsIndicators: ForensicsIndicator[]
  forensicsLimitations: string[]
  deficiencies: DeficiencyNotice[]
  verifications: VerificationResult[]
  documentVerificationRuns?: DocumentVerificationRun[]
  reviewNotes: ReviewNote[]
  auditEvents: AuditEvent[]
  validationRunId?: string
  validationRunStatus?: string
  scoreBreakdown?: {
    score?: number
    configVersion?: string
    weights?: Record<string, number>
    contributions?: ScoreContribution[]
    notes?: string[]
    processingComplete?: boolean
    disclaimer?: string
  }
  scrutinySummary?: Record<string, unknown>
  lastTransitionAt?: string | null
  lastTransitionNote?: string | null
}

export interface ScrutinyStats {
  totalInQueue: number
  awaitingReview: number
  withDeficiencies: number
  requiringManualReview: number
  statusDistribution: { status: string; count: number }[]
  labeledAsDemo: true
}

export interface ActivityItem {
  id: string
  title: string
  detail: string
  timestamp: string
  severity?: FindingSeverity
}

export interface ApiHealth {
  status: string
  environment: string
  database: string
  storageBackend: string
  demoAuth: boolean
}

export interface AdminUser {
  id: string
  name: string
  email: string
  role: UserRole
  institutionId?: string | null
  institutionName?: string | null
  isActive: boolean
  createdAt?: string | null
}

export interface AdminInstitution {
  id: string
  name: string
  code: string
  state: string
  type: string
}

export interface AdminCategory {
  id: string
  code: string
  name: string
  description: string
  requiredDocuments: Array<{
    code: string
    name: string
    mandatory: boolean
    allowedTypes: string[]
  }>
  isActive: boolean
}

export interface AdminRuleVersion {
  id: string
  version: string
  definition: Record<string, unknown>
  status: string
  changeReason?: string
  createdById?: string | null
  effectiveFrom?: string | null
  effectiveTo?: string | null
  publishedAt?: string | null
  createdAt: string
}

export interface AdminRule {
  id: string
  ruleCode: string
  name: string
  description: string
  handbookRef: string
  verifiedSourceRef?: string
  isSynthetic: boolean
  isActive: boolean
  currentVersion: string
  versions: AdminRuleVersion[]
}

export interface AdminSetting {
  key: string
  value: Record<string, unknown>
  description: string
  updatedById?: string | null
  changeReason?: string
  updatedAt?: string | null
}

export interface AdminAuditEvent {
  id: string
  action: string
  actor: string
  actorRole?: string
  timestamp: string
  detail: string
  applicationId?: string | null
  entityType?: string | null
  entityId?: string | null
  metadata?: Record<string, unknown>
}

export interface AdminAuditPage {
  items: AdminAuditEvent[]
  total: number
  limit: number
  offset: number
}

export interface AdminStats {
  userCount: number
  activeRuleCount: number
  categoryCount: number
  auditEvents24h: number
  liveVerificationEnabled: boolean
}
