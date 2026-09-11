import { useState, useEffect, useCallback } from 'react'
import {
  getQualityMetrics,
  listRuns,
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

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return {
    metrics,
    runs,
    loading,
    error,
    refetch: fetchData,
  }
}
