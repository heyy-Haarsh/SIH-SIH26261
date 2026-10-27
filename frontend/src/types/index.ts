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

export type ApplicationStage =
  | 'draft'
  | 'awaiting_scrutiny'
  | 'under_scrutiny'
  | 'awaiting_applicant'
  | 'decided'

export interface ApplicationMetrics {
  total: number
  inOfficerQueue: number
  byStage: Record<ApplicationStage, number>
  stageLabels: Record<ApplicationStage, string>
  byStatus: Record<string, number>
  requiresManualReview: number
  openClarifications: number
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
  /** Open issues, counted exactly as the scrutiny review counts them. */
  findingCount: number
  /** Whose turn it is — the same model on every dashboard and list. */
  stage?: ApplicationStage
  stageLabel?: string
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
  documentCheck?: DocumentCheck | null
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
  appVersion?: string
  maxUploadMb?: number | null
  autoExtractOnUpload?: boolean | null
  enableLiveVerification?: boolean | null
  enableNominatimGeocode?: boolean | null
  limitations?: string[]
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
  enforcement?: Record<string, string>
}

export interface AdminAuditEvent {
  id: string
  action: string
  label?: string
  category?: string
  actor: string
  actorId?: string | null
  applicationNumber?: string | null
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
  applications?: ApplicationMetrics
}

// ---- Applicant-facing view (no extracted fields / scores / forensics / technical codes) ----

export type TypeMatchState = 'matched' | 'mismatch' | 'unclear' | 'not_checked'
export type ClarityState = 'clear' | 'unclear' | 'unreadable' | 'not_checked'

export interface DocumentCheck {
  typeMatch: TypeMatchState
  typeMatchMessage: string
  expectedType: string
  detectedType?: string | null
  clarity: ClarityState
  clarityMessage: string
  languageNote?: string | null
  needsAttention: boolean
}

export interface UploadPolicy {
  maxUploadMb: number
  maxUploadBytes: number
  allowedExtensions: string[]
  ocrAvailable: boolean
  ocrLanguages: string[]
  marathiSupported: boolean
  ocrMessage: string
}

export type ApplicantUploadStatus = 'not_uploaded' | 'uploaded' | 'replaced' | 'needs_attention'

export interface ApplicantDocumentVersion {
  version: number
  fileName: string
  uploadedAt: string
  sizeBytes: number
}

export interface ApplicantDocument {
  id: string
  fileName: string
  version: number
  uploadedAt: string
  sizeBytes: number
  documentCheck?: DocumentCheck | null
  previousVersions: ApplicantDocumentVersion[]
}

export interface ApplicantRequirement {
  code: string
  name: string
  mandatory: boolean
  allowedTypes: string[]
  uploadStatus: ApplicantUploadStatus
  uploadStatusLabel: string
  document?: ApplicantDocument | null
}

export interface ApplicantDeficiency {
  id: string
  title: string
  description: string
  status: 'open' | 'responded' | 'closed'
  applicantResponse?: string | null
  respondedAt?: string | null
  createdAt: string
  resolvedAt?: string | null
}

export interface ApplicantHistoryEntry {
  id: string
  timestamp: string
  label: string
  detail?: string | null
}

export interface ApplicantApplication {
  id: string
  applicationNumber: string
  institutionName: string
  category: string
  categoryCode: string
  programName: string
  academicYear: string
  status: ApplicationStatus
  statusLabel: string
  statusMessage: string
  submittedAt?: string | null
  requirements: ApplicantRequirement[]
  deficiencies: ApplicantDeficiency[]
  history: ApplicantHistoryEntry[]
  canUpload: boolean
  canResubmit: boolean
  resubmitBlockers: string[]
  requiredTotal: number
  requiredUploaded: number
}

export interface ApplicantApplicationSummary {
  id: string
  applicationNumber: string
  institutionName: string
  category: string
  programName: string
  academicYear: string
  status: ApplicationStatus
  statusLabel: string
  submittedAt?: string | null
  openClarifications: number
  requiredTotal: number
  requiredUploaded: number
}

// ---- Scrutiny review (officer-facing; never sent to applicants) ----------------------

export interface HandbookReference {
  status: 'verified' | 'unverified'
  edition?: string | null
  section?: string | null
  page?: string | null
  title?: string | null
  note: string
}

export type IssueSeverity = 'failed' | 'manual_review' | 'warning' | 'info'
export type IssueStatus = 'open' | 'resolved' | 'waived' | 'accepted'

export interface IssueEvidence {
  text: string
  documentId?: string | null
  documentName?: string | null
  pageReference?: string | null
}

export interface ScrutinyIssue {
  key: string
  title: string
  explanation: string
  severity: IssueSeverity
  status: IssueStatus
  source: string
  layer: string
  documentId?: string | null
  documentName?: string | null
  requirementCode?: string | null
  relatedDocuments: Array<{ id: string; name: string }>
  applicantAction?: string | null
  handbook: HandbookReference
  findingIds: string[]
  checkIds: string[]
  occurrences: number
  evidence: IssueEvidence[]
}

export interface DocumentIssueGroup {
  documentId?: string | null
  documentName: string
  requirementCode?: string | null
  scope: 'document' | 'cross_document' | 'application'
  issues: ScrutinyIssue[]
  openCount: number
  highestSeverity?: IssueSeverity | null
}

export interface DocumentCard {
  id: string
  name: string
  requirementCode: string
  fileName: string
  version: number
  mimeType: string
  sizeBytes: number
  uploadedAt: string
  pageCount?: number | null
  ruleValidationStatus?: string | null
  externalVerificationStatus?: string | null
  reviewStatus?: string | null
  documentCheck?: DocumentCheck | null
  openIssueCount: number
  highestSeverity?: IssueSeverity | null
  canPreview: boolean
}

export interface DecisionContext {
  status: string
  clarificationRequests: Array<{
    id: string
    title: string
    description: string
    status: string
    applicantResponse?: string | null
    createdAt: string
    respondedAt?: string | null
  }>
  finalDecision?: 'recommended' | 'rejected' | null
  finalDecisionReason?: string | null
  finalDecisionBy?: string | null
  finalDecisionAt?: string | null
  mustCorrect: string[]
  clarificationDraftTitle: string
  clarificationDraftBody: string
  rejectionDraftBody: string
}

export interface ScrutinyReview {
  applicationId: string
  applicationNumber: string
  institutionName: string
  status: string
  generatedAt: string
  validationRunId?: string | null
  validationCompletedAt?: string | null
  documents: DocumentCard[]
  missingDocuments: Array<{ code: string; name: string; mandatory: boolean }>
  issueGroups: DocumentIssueGroup[]
  openIssueCount: number
  resolvedIssueCount: number
  historicalFindingCount: number
  limitations: string[]
  decision: DecisionContext
  disclaimer: string
}

export type StageStatus =
  | 'pass'
  | 'warning'
  | 'failed'
  | 'manual_review'
  | 'unavailable'
  | 'not_run'

export interface PipelineCheck {
  id: string
  title: string
  outcome: string
  severity: IssueSeverity
  status: string
  detail: string
  source?: string | null
  mode?: 'real' | 'simulated' | 'unavailable' | 'local' | null
  limitations: string[]
  resolutionReason?: string | null
  resolvable: boolean
  resolveKind?: 'finding' | 'check' | 'reconciliation' | 'forensics' | null
  handbook?: HandbookReference | null
}

export interface PipelineStage {
  key: 'intake' | 'classification' | 'layer1' | 'layer2' | 'layer3'
  title: string
  status: StageStatus
  summary: string
  details: Array<{ label: string; value: string }>
  checks: PipelineCheck[]
  limitations: string[]
}

export interface DocumentReport {
  document: DocumentCard
  stages: PipelineStage[]
  issues: ScrutinyIssue[]
  extractedFields: ExtractedField[]
  versions: Array<{
    version: number
    fileName: string
    uploadedAt: string
    sizeBytes: number
    sha256: string
    isCurrent: boolean
  }>
  disclaimer: string
}

export interface HandbookReferenceAdmin {
  id: string
  referenceKey: string
  edition: string
  section: string
  page: string
  title: string
  sourceNote: string
  verified: boolean
  verifiedBy?: string | null
  verifiedAt?: string | null
  updatedAt?: string | null
}

// ---- Administrator: integrations, system health, rule import/draft, audit facets ----

export type IntegrationHealth =
  | 'healthy'
  | 'degraded'
  | 'unavailable'
  | 'not_configured'
  | 'disabled'
  | 'simulated'

export interface IntegrationLastCheck {
  checkedAt: string
  ok: boolean | null
  message: string
}

export interface Integration {
  id: string
  label: string
  category: string
  description: string
  health: IntegrationHealth
  mode: string
  message: string
  configured: boolean
  deploymentEnabled: boolean
  adminEnabled: boolean
  effectiveEnabled: boolean
  requiresCredentials: boolean
  credentialsConfigured: boolean | null
  details: Record<string, unknown>
  limitations: string[]
  canToggle: boolean
  adminReason: string
  adminChangedBy: string
  adminChangedAt: string | null
  lastCheck: IntegrationLastCheck | null
}

export interface IntegrationList {
  items: Integration[]
  summary: Record<string, number>
}

export interface HealthComponent {
  id: string
  label: string
  category: string
  health: IntegrationHealth
  message: string
  limitations: string[]
}

export interface SystemHealthActivity {
  windowHours: number
  applicationsByStatus: Record<string, number>
  applicationsTotal: number
  validationRuns: number
  validationRunsFailed: number
  extractionRuns: number
  extractionRunsFailed: number
  extractionRunsNeedingAttention: number
  verificationChecksUnavailable: number | null
  lastAuditEventAt: string | null
  lastValidationAt: string | null
  auditEvents: number
}

export interface SystemHealth {
  status: 'ok' | 'degraded' | 'unavailable'
  checkedAt: string
  environment: string
  version: string
  components: HealthComponent[]
  integrations: HealthComponent[]
  integrationSummary: Record<string, number>
  activity: SystemHealthActivity
  warnings: string[]
}

export interface RuleImportItemResult {
  index: number
  code: string
  name?: string
  action: 'create_rule_draft' | 'add_draft_version' | 'invalid'
  valid: boolean
  errors: string[]
  warnings: string[]
  version: string
}

export interface RuleImportValidation {
  valid: boolean
  fileErrors: string[]
  results: RuleImportItemResult[]
  willCreate: number
  note: string
}

export interface RuleImportResult {
  created: Array<{ code: string; version: string; action: string; ruleId: string; activated: boolean }>
  activated: number
  message: string
}

export interface RuleDraftProposal {
  requiresReview: boolean
  executable: boolean
  confidence: 'high' | 'low'
  mode: 'new_version_of_existing_rule' | 'new_rule'
  interpretation: string[]
  warnings: string[]
  sourceText: string
  draft: {
    code: string
    name: string
    description: string
    version: string
    isSynthetic: boolean
    handbookRef: string
    verifiedSourceRef: string
    definition: Record<string, unknown>
    changeReason: string
    targetRuleCode: string | null
  }
  validation: { valid: boolean; errors: string[]; warnings: string[] }
}

export interface RuleUsage {
  ruleCode: string
  currentVersion: string
  findingsByVersion: Record<string, number>
  note: string
}

export interface FacetValue {
  value: string
  count: number
}

export interface AuditFacets {
  categories: FacetValue[]
  actions: FacetValue[]
  actorRoles: FacetValue[]
  entityTypes: FacetValue[]
  total: number
  firstEventAt: string | null
  lastEventAt: string | null
}

export interface AdminAuditDetail extends AdminAuditEvent {
  related: AdminAuditEvent[]
}
