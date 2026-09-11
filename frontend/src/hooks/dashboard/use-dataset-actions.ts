import { useState, useCallback } from 'react'
import { createDatasetSnapshot, type CreateSnapshotResponse } from '@/lib/api/runs'
import { toast } from 'sonner'

export function useDatasetActions(onSnapshotCreated?: () => void) {
  const [isExporting, setIsExporting] = useState(false)

  const handleExportSnapshot = useCallback(async () => {
    setIsExporting(true)
    try {
      const res: CreateSnapshotResponse = await createDatasetSnapshot()
      toast.success('Dataset snapshot exported successfully', {
        description: `Saved ${res.item_count} labeled records to ${res.snapshot_id}`,
      })
      if (onSnapshotCreated) {
        onSnapshotCreated()
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to export snapshot'
      toast.error('Export failed', {
        description: msg,
      })
    } finally {
      setIsExporting(false)
    }
  }, [onSnapshotCreated])

  return {
    isExporting,
    handleExportSnapshot,
  }
}
