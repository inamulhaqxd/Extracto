import { useState, useCallback } from 'react'
import { getRunInspections, type RunInspectionItem } from '@/lib/api/runs'

export function useRunInspection() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [inspectionItems, setInspectionItems] = useState<RunInspectionItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const openInspection = useCallback(async (runId: string) => {
    setSelectedRunId(runId)
    setLoading(true)
    setError(null)
    try {
      const items = await getRunInspections(runId)
      setInspectionItems(items)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch run inspections'
      setError(msg)
      setInspectionItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  const closeInspection = useCallback(() => {
    setSelectedRunId(null)
    setInspectionItems([])
    setError(null)
  }, [])

  return {
    selectedRunId,
    inspectionItems,
    loading,
    error,
    openInspection,
    closeInspection,
  }
}
