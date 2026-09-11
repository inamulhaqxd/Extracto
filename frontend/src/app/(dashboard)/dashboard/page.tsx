'use client'

import Link from 'next/link'
import { Button, buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { RefreshCw, Plus } from 'lucide-react'
import { useQualityDashboard } from '@/hooks/dashboard/use-quality-dashboard'
import { useRunInspection } from '@/hooks/dashboard/use-run-inspection'
import { QualityMetricCards } from '@/components/dashboard/quality-metric-cards'
import { ReviewedRunsTable } from '@/components/dashboard/reviewed-runs-table'
import { RunInspectionDialog } from '@/components/dashboard/run-inspection-dialog'

export default function DashboardPage() {
  const { metrics, runs, loading, error, refetch, removeRun, removeAllRuns } = useQualityDashboard()
  const {
    selectedRunId,
    inspectionItems,
    loading: inspectionLoading,
    error: inspectionError,
    openInspection,
    closeInspection,
  } = useRunInspection()

  return (
    <div className="flex-1 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Overview of RFP extraction runs, processing status, and review metrics
          </p>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <Button
            variant="outline"
            size="sm"
            onPress={refetch}
            isDisabled={loading}
            className="gap-1.5 text-xs"
          >
            <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Link
            href="/rfp"
            className={cn(buttonVariants({ size: 'sm' }), "gap-1.5 text-xs")}
          >
            <Plus className="size-3.5" />
            New Extraction
          </Link>
        </div>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-600 dark:text-rose-400 flex items-center justify-between">
          <span>{error}</span>
          <Button size="sm" variant="ghost" onPress={refetch} className="text-xs h-7">
            Retry
          </Button>
        </div>
      )}

      {/* KPI Metric Cards */}
      <QualityMetricCards metrics={metrics} totalRuns={runs.length} loading={loading} />

      {/* Recent Processing Runs Table */}
      <ReviewedRunsTable
        runs={runs}
        loading={loading}
        onInspect={openInspection}
        onDelete={removeRun}
        onDeleteAll={removeAllRuns}
      />

      {/* Per-Run Detailed Resolution Inspection Dialog */}
      <RunInspectionDialog
        isOpen={Boolean(selectedRunId)}
        runId={selectedRunId}
        items={inspectionItems}
        loading={inspectionLoading}
        error={inspectionError}
        onClose={closeInspection}
      />
    </div>
  )
}
