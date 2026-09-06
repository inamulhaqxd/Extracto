'use client'

import { useCallback, useState } from 'react'
import type { RunStageKey } from '@/components/runs/run-stepper'

export function useRunStage() {
  const [stage, setStage] = useState<RunStageKey>('upload')

  const goToUpload = useCallback(() => setStage('upload'), [])
  const goToMonitor = useCallback(() => setStage('monitor'), [])
  const goToReview = useCallback(() => setStage('review'), [])
  const goToExport = useCallback(() => setStage('export'), [])

  return { stage, goToUpload, goToMonitor, goToReview, goToExport }
}
