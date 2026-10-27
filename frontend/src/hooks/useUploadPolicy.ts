import { useEffect, useState } from 'react'
import { useRole } from '@/app/RoleContext'
import { FALLBACK_POLICY } from '@/lib/fileValidation'
import { api } from '@/services/api'
import type { UploadPolicy } from '@/types'

/** Server-provided upload limits (falls back to built-in defaults if the API is unreachable). */
export function useUploadPolicy() {
  const { role } = useRole()
  const [policy, setPolicy] = useState<UploadPolicy | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .uploadPolicy(role)
      .then((p) => {
        if (!cancelled) setPolicy(p)
      })
      .catch(() => {
        if (!cancelled) setPolicy(null)
      })
    return () => {
      cancelled = true
    }
  }, [role])

  return {
    policy,
    filePolicy: policy
      ? {
          maxUploadBytes: policy.maxUploadBytes,
          maxUploadMb: policy.maxUploadMb,
          allowedExtensions: policy.allowedExtensions,
        }
      : FALLBACK_POLICY,
  }
}
