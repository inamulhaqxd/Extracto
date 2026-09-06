'use client'

import { useCallback, useRef, useState } from 'react'
import { buildMockRun } from '@/lib/mock-run'
import type { DecisionStatus, ProcessingRun } from '@/types'

const MOCK_PROGRESS_STEPS: Array<Pick<ProcessingRun, 'progress' | 'current_step'>> = [
  { progress: 30, current_step: 'Extracting technical specifications from reference PDF' },
  { progress: 55, current_step: 'Evaluating 5 requirements with Compliance Engine' },
  { progress: 90, current_step: 'Populating Excel workbook and generating Compliance Summary' },
  { progress: 100, current_step: 'Completed successfully' },
]

const MOCK_TICK_MS = 900

export function useMockRun() {
  const [run, setRun] = useState<ProcessingRun | null>(null)
  const activeRunId = useRef<string | null>(null)

  const start = useCallback(() => {
    const runId = crypto.randomUUID()
    activeRunId.current = runId

    setRun(
      buildMockRun({
        id: runId,
        status: 'processing',
        progress: 12,
        current_step: 'Analyzing Excel template and mapping empty slots',
      })
    )

    MOCK_PROGRESS_STEPS.forEach((step, i) => {
      setTimeout(
        () => {
          if (activeRunId.current !== runId) return
          setRun((prev) =>
            prev
              ? {
                  ...prev,
                  ...step,
                  status: i === MOCK_PROGRESS_STEPS.length - 1 ? 'completed' : 'processing',
                }
              : prev
          )
        },
        MOCK_TICK_MS * (i + 1)
      )
    })
  }, [])

  const reset = useCallback(() => {
    activeRunId.current = null
    setRun(null)
  }, [])

  const decide = useCallback((id: string, status: DecisionStatus, overrideValue?: string) => {
    setRun((prev) =>
      prev
        ? {
            ...prev,
            decisions: prev.decisions.map((d) =>
              d.id === id ? { ...d, status, override_value: overrideValue ?? d.override_value } : d
            ),
          }
        : prev
    )
  }, [])

  return { run, start, reset, decide }
}
