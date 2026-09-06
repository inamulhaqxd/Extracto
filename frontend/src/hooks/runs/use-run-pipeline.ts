'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import type { DecisionStatus, ProcessingRun } from '@/types'
import {
  createRun,
  getRun,
  submitRunReview,
  transformBackendRun,
  uploadExcel,
  uploadPdf,
} from '@/lib/api/runs'

const POLL_INTERVAL_MS = 1500

export function useRunPipeline() {
  const [run, setRun] = useState<ProcessingRun | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const activeRunId = useRef<string | null>(null)
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null)

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [stopPolling])

  const startWithFiles = useCallback(
    async (pdfFile: File, excelFile: File, modelTag?: string | null) => {
      setLoading(true)
      setError(null)
      stopPolling()

      try {
        setRun({
          id: 'temp-upload',
          status: 'processing',
          progress: 5,
          current_step: 'Uploading reference PDF and Excel template...',
          pdf_filename: pdfFile.name,
          excel_filename: excelFile.name,
          model: modelTag || 'Default',
          decisions: [],
          created_at: new Date().toISOString(),
        })

        // Upload both files in parallel
        const [pdfRes, excelRes] = await Promise.all([
          uploadPdf(pdfFile),
          uploadExcel(excelFile),
        ])

        // Create the run
        const createRes = await createRun({
          pdf_document_id: pdfRes.document_id,
          workbook_id: excelRes.workbook_id,
          model_name: modelTag,
        })

        const runId = createRes.run_id
        activeRunId.current = runId
        setRun(transformBackendRun(createRes))

        // Start polling for real-time progress
        pollTimerRef.current = setInterval(async () => {
          if (activeRunId.current !== runId) return

          try {
            const currentStatus = await getRun(runId)
            if (activeRunId.current !== runId) return

            const transformed = transformBackendRun(currentStatus)
            setRun(transformed)

            if (
              transformed.status === 'completed' ||
              transformed.status === 'failed' ||
              transformed.status === 'cancelled'
            ) {
              stopPolling()
            }
          } catch (pollErr: unknown) {
            console.warn('Poll error:', pollErr)
          }
        }, POLL_INTERVAL_MS)
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to start pipeline'
        setError(msg)
        console.error('Pipeline start failed:', err)

        setRun({
          id: 'failed-start',
          status: 'failed',
          progress: 0,
          current_step: `Pipeline failed: ${msg}`,
          pdf_filename: pdfFile.name,
          excel_filename: excelFile.name,
          model: modelTag || 'Default',
          error_message: msg,
          decisions: [],
          created_at: new Date().toISOString(),
        })
      } finally {
        setLoading(false)
      }
    },
    [stopPolling]
  )

  const reset = useCallback(() => {
    stopPolling()
    activeRunId.current = null
    setRun(null)
    setError(null)
  }, [stopPolling])

  const decide = useCallback(
    async (id: string, status: DecisionStatus, overrideValue?: string) => {
      // 1. Optimistic local update
      setRun((prev) =>
        prev
          ? {
              ...prev,
              decisions: prev.decisions.map((d) =>
                d.id === id
                  ? { ...d, status, override_value: overrideValue ?? d.override_value }
                  : d
              ),
            }
          : prev
      )

      // 2. Persist override to backend if run exists
      const currentRunId = activeRunId.current
      if (currentRunId) {
        try {
          await submitRunReview(currentRunId, [
            {
              requirement_id: id,
              status: status === 'approved' ? 'COMPLIANT' : 'NON_COMPLIANT',
              matched_value: overrideValue,
            },
          ])
        } catch (err: unknown) {
          console.warn('Failed to persist review override to backend:', err)
        }
      }
    },
    []
  )

  return { run, loading, error, startWithFiles, reset, decide }
}
