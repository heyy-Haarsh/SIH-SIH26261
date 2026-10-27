export interface ApplicationFormValues {
  institutionName: string
  program: string
  year: string
}

export type ApplicationFormErrors = Partial<Record<keyof ApplicationFormValues, string>>

const YEAR_PATTERN = /^\d{4}-\d{2}$/

/** Mirrors the server rules (backend ApplicationCreateIn); the server remains authoritative. */
export function validateApplicationForm(input: ApplicationFormValues): {
  values: ApplicationFormValues
  errors: ApplicationFormErrors
} {
  const values: ApplicationFormValues = {
    institutionName: input.institutionName.replace(/\s+/g, ' ').trim(),
    program: input.program.trim(),
    year: input.year.trim(),
  }
  const errors: ApplicationFormErrors = {}

  if (values.institutionName.length < 3) {
    errors.institutionName = 'Enter the institution name (at least 3 characters).'
  } else if (!/\p{L}/u.test(values.institutionName)) {
    errors.institutionName = 'The institution name must contain letters.'
  } else if (values.institutionName.length > 255) {
    errors.institutionName = 'The institution name is too long (max 255 characters).'
  }
  if (!values.program) errors.program = 'Enter the program name.'
  if (!YEAR_PATTERN.test(values.year)) errors.year = 'Use the format 2025-26.'

  return { values, errors }
}
