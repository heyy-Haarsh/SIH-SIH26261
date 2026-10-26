export type UserRole = 'applicant' | 'officer' | 'admin'

export type ApplicationStatus =
  | 'draft'
  | 'submitted'
  | 'awaiting_review'
  | 'under_review'
  | 'deficiency'
  | 'manual_review'
  | 'approved'
  | 'rejected'
  | 'resubmitted'

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
  /** Demo prioritization aid — not proof of fraud or compliance */
  priorityScore?: number
  assignedOfficer?: string
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
}

export interface ExtractedField {
  id: string
  fieldName: string
  value: string
  confidence: number | null
  pageReference: string | null
  sourceDocumentId: string
  sourceDocumentName: string
  correctedValue?: string
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

export interface Discrepancy {
  id: string
  fieldName: string
  values: { documentName: string; value: string; page?: string }[]
  severity: FindingSeverity
  status: FindingStatus
}

export interface VerificationResult {
  id: string
  claim: string
  status: VerificationStatus
  source: VerificationSource
  detail: string
  checkedAt: string | null
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
  verifications: VerificationResult[]
  reviewNotes: ReviewNote[]
  auditEvents: AuditEvent[]
  validationRunId?: string
  validationRunStatus?: string
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
