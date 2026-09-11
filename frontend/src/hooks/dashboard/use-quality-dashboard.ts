import { useState, useEffect, useCallback } from 'react'
import {
  getQualityMetrics,
  listRuns,
  deleteRun,
  deleteAllRuns,
  type QualityMetricsResponse,
  type BackendRunResponse,
} from '@/lib/api/runs'

export function useQualityDashboard() {
  const [metrics, setMetrics] = useState<QualityMetricsResponse | null>(null)
  const [runs, setRuns] = useState<BackendRunResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [m, r] = await Promise.all([
        getQualityMetrics().catch(() => null),
        listRuns().catch(() => []),
      ])
      setMetrics(m)
      setRuns(r)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load quality metrics'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  const removeRun = useCallback(
    async (runId: string) => {
      try {
        await deleteRun(runId)
        await fetchData()
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to delete run'
        setError(msg)
        throw err
      }
    },
    [fetchData]
  )

  const removeAllRuns = useCallback(async () => {
    try {
      await deleteAllRuns()
      await fetchData()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete all runs'
      setError(msg)
      throw err
    }
  }, [fetchData])

  useEffect(() => {
    let ignore = false
    async function load() {
      try {
        const [m, r] = await Promise.all([
          getQualityMetrics().catch(() => null),
          listRuns().catch(() => []),
        ])
        if (!ignore) {
          setMetrics(m)
          setRuns(r)
          setLoading(false)
        }
      } catch (err: unknown) {
        if (!ignore) {
          const msg = err instanceof Error ? err.message : 'Failed to load quality metrics'
          setError(msg)
          setLoading(false)
        }
      }
    }
    load()
    return () => {
      ignore = true
    }
  }, [])

  return {
    metrics,
    runs,
    loading,
    error,
    refetch: fetchData,
    removeRun,
    removeAllRuns,
  }
}

