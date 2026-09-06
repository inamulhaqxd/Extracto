import { useMemo } from 'react'
import { isLowConfidence } from '@/lib/confidence'
import type { RequirementDecision } from '@/types'

export function useReviewSummary(decisions: RequirementDecision[]) {
  return useMemo(() => {
    const averageConfidence =
      decisions.length === 0
        ? 0
        : decisions.reduce((sum, d) => sum + d.confidence, 0) / decisions.length

    return {
      total: decisions.length,
      needsAttention: decisions.filter((d) => isLowConfidence(d.confidence)).length,
      pending: decisions.filter((d) => d.status === 'pending').length,
      averageConfidence,
    }
  }, [decisions])
}
