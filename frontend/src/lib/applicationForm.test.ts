import { describe, expect, it } from 'vitest'
import { validateApplicationForm } from '@/lib/applicationForm'

const ok = { institutionName: 'Shivaji Institute of Technology', program: 'B.Tech CSE', year: '2025-26' }

describe('validateApplicationForm', () => {
  it('accepts a complete form and normalises whitespace', () => {
    const { values, errors } = validateApplicationForm({ ...ok, institutionName: '  Shivaji   Institute  ' })
    expect(errors).toEqual({})
    expect(values.institutionName).toBe('Shivaji Institute')
  })

  it('requires the institution name', () => {
    for (const bad of ['', '   ', 'ab', '12345', '----']) {
      const { errors } = validateApplicationForm({ ...ok, institutionName: bad })
      expect(errors.institutionName, bad).toBeTruthy()
    }
  })

  it('accepts a Marathi institution name', () => {
    const { errors } = validateApplicationForm({ ...ok, institutionName: 'शिवाजी तंत्रनिकेतन' })
    expect(errors.institutionName).toBeUndefined()
  })

  it('requires a program and a yyyy-yy academic year', () => {
    expect(validateApplicationForm({ ...ok, program: ' ' }).errors.program).toBeTruthy()
    expect(validateApplicationForm({ ...ok, year: '2025' }).errors.year).toBeTruthy()
  })
})
