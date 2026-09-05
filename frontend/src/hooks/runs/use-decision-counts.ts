import { useMemo } from 'react'
import type { DecisionStatus, RequirementDecision } from '@/types'

export function useDecisionCounts(decisions: RequirementDecision[]) {
  return useMemo(() => {
    return decisions.reduce(
      (acc, d) => {
        acc[d.status] += 1
        return acc
      },
      { pending: 0, approved: 0, rejected: 0, overridden: 0 } as Record<DecisionStatus, number>
    )
  }, [decisions])
}
