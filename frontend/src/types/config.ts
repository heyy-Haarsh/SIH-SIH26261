// ---- Category configuration (administrator) --------------------------------------------

export type InfoFieldType = 'text' | 'textarea' | 'number' | 'date' | 'select' | 'email' | 'boolean'

export interface InfoFieldDef {
  key: string
  label: string
  help_text?: string
  type: InfoFieldType
  required?: boolean
  options?: string[]
  min_length?: number
  max_length?: number
  min?: number
  max?: number
}

export type ConfigState = 'published' | 'unpublished_changes' | 'unpublished'

export interface ConfigCategorySummary {
  id: string
  code: string
  name: string
  description: string
  isActive: boolean
  status: 'active' | 'inactive'
  infoFieldCount: number
  requiredDocuments: number
  optionalDocuments: number
  activeRules: number
  draftRules: number
  totalRules: number
  configState: ConfigState
  configVersion: number | null
  updatedAt: string | null
}

export interface ConfigRequirement {
  id: string
  code: string
  documentTypeCode: string
  name: string
  description: string
  mandatory: boolean
  allowedTypes: string[]
  maxSizeMb: number | null
  expectedFields: string[]
  displayOrder: number
  isActive: boolean
  activeRules: number
  draftRules: number
  inactiveRules: number
  totalRules: number
  status: 'active' | 'inactive'
  updatedAt: string | null
}

export interface ConfigValidation {
  valid: boolean
  errors: string[]
  warnings: string[]
  counts: { infoFields: number; requirements: number; activeRules: number }
}

export interface ConfigVersionRow {
  id: string
  version: number
  status: 'published' | 'superseded'
  summary: string
  publishedAt: string | null
  publishedBy: string | null
  requirementCount: number
  ruleCount: number
}

export interface ConfigCategoryDetail extends ConfigCategorySummary {
  infoFields: InfoFieldDef[]
  requirements: ConfigRequirement[]
  validation: ConfigValidation
  pendingChanges: string[]
  versions: ConfigVersionRow[]
  supportedFieldTypes: InfoFieldType[]
}

export interface RuleExplanation {
  condition: string
  onPass: string
  onFail: string
  onUnable: string
  severity: string
  summary: string
}

export interface RuleValidationReport {
  valid: boolean
  errors: string[]
  warnings: string[]
  unsupported: string[]
  requiresSource: boolean
  requiredInputs: string[]
  validatedAt?: string
  explanation?: RuleExplanation | null
  definition?: unknown
}

export interface RuleVersionInfo {
  id: string
  version: number
  status: 'draft' | 'published' | 'retired'
  authoringMode: 'plain' | 'json'
  naturalLanguage: string
  title: string
  description: string
  sourceReference: string
  notes: string
  definition: Record<string, unknown>
  schemaVersion: number
  validation: Partial<RuleValidationReport>
  changeSummary: string
  createdAt: string | null
  updatedAt: string | null
  publishedAt: string | null
  explanation: RuleExplanation | null
}

export interface ConfigRule {
  id: string
  code: string
  title: string
  description: string
  ruleType: string
  status: 'active' | 'draft' | 'inactive' | 'superseded'
  sourceReference: string
  severity?: string
  activeVersion: number | null
  draftVersion: number | null
  latestVersion: number | null
  updatedAt: string | null
  categoryId: string
  requirementId: string
  requirementCode: string | null
  requirementName: string | null
  category: { id: string; code: string | null; name: string | null } | null
  configVersion?: number | null
  versions?: RuleVersionInfo[]
  notes?: string
}

export interface RequirementRulesResponse {
  category: { id: string; code: string; name: string }
  requirement: ConfigRequirement
  rules: ConfigRule[]
}

export interface RuleDefinitionSchema {
  schemaVersion: number
  checkTypes: Array<{ type: string; label: string; params: string[]; required: string[]; needsSource: boolean }>
  operators: string[]
  formats: string[]
  valueTypes: string[]
  onFail: string[]
  knownFields: string[]
  example: Record<string, unknown>
}

export interface RuleSuggestion {
  definition: Record<string, unknown> | null
  assumptions: string[]
  unsupported: string[]
  explanation?: RuleExplanation
  validation?: RuleValidationReport
}

export interface RuleDryRunResult {
  validation: RuleValidationReport
  result: { state: string; message: string; inputs: Record<string, unknown> } | null
}

// ---- Applicant: published category configuration ---------------------------------------

export interface PublicInfoField {
  key: string
  label: string
  helpText: string
  type: InfoFieldType
  required: boolean
  options: string[]
  minLength?: number | null
  maxLength?: number | null
  min?: number | null
  max?: number | null
  value?: unknown
}

export interface PublicRequirement {
  code: string
  name: string
  description: string
  mandatory: boolean
  allowedTypes: string[]
  maxSizeMb: number | null
  checks: Array<{ title: string; meaning: string }>
}

export interface PublicCategoryConfig {
  code: string
  name: string
  description: string
  configVersion: number
  infoFields: PublicInfoField[]
  requirements: PublicRequirement[]
  declarations: string[]
  limitations: string[]
}

export interface ApplicantCategoryOption {
  code: string
  name: string
  description: string
  configVersion: number | null
  infoFieldCount: number
  mandatoryCount: number
  optionalCount: number
  available: boolean
}

export interface RuleCheckRow {
  id: string
  requirementCode: string
  ruleCode: string
  ruleTitle: string
  ruleVersion: number
  configVersion: number
  documentId: string | null
  documentVersion: number | null
  state: string
  stateLabel: string
  severity: string
  message: string
  isCurrent: boolean
  createdAt: string | null
}

export interface ApplicantCheck {
  title: string
  meaning: string
  state: 'passed' | 'failed' | 'manual_review' | 'unable_to_evaluate' | 'pending' | 'source_unavailable'
  stateLabel: string
  message: string
  documentVersion?: number | null
  ruleVersion?: number | null
  configVersion?: number | null
}
