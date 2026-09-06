import { useMemo } from 'react'
import type { RequirementDecision } from '@/types'

export function useSortedDecisions(decisions: RequirementDecision[]) {
  return useMemo(
    () => [...decisions].sort((a, b) => a.confidence - b.confidence),
    [decisions]
  )
}
