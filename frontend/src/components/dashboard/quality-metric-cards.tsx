'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CheckCircle2, AlertTriangle, Database, Layers } from 'lucide-react'
import type { QualityMetricsResponse } from '@/lib/api/runs'

interface QualityMetricCardsProps {
  metrics: QualityMetricsResponse | null
  loading: boolean
}

export function QualityMetricCards({ metrics, loading }: QualityMetricCardsProps) {
  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <div className="h-4 w-24 rounded bg-muted/60" />
              <div className="size-4 rounded-full bg-muted/60" />
            </CardHeader>
            <CardContent>
              <div className="h-8 w-16 rounded bg-muted/60 mb-1" />
              <div className="h-3 w-32 rounded bg-muted/40" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const accuracyPct = metrics
    ? Math.round(metrics.exact_correction_accuracy * 100)
    : 0

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card className="border-border/60">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Exact Match Accuracy
          </CardTitle>
          <CheckCircle2 className="size-4 text-emerald-500" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold tracking-tight">
            {metrics ? `${accuracyPct}%` : 'N/A'}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Status and value match reviewer ground truth
          </p>
        </CardContent>
      </Card>

      <Card className="border-border/60">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Reviewed Examples
          </CardTitle>
          <Layers className="size-4 text-primary" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold tracking-tight">
            {metrics?.total_reviewed_examples ?? 0}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Across {metrics?.reviewed_runs ?? 0} reviewed runs ({metrics?.total_runs ?? 0} total)
          </p>
        </CardContent>
      </Card>

      <Card className="border-border/60">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Review Required Flags
          </CardTitle>
          <AlertTriangle className="size-4 text-amber-500" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold tracking-tight">
            {metrics?.low_confidence_failures ?? 0}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Confidence &lt; 70% or flagged for human inspection
          </p>
        </CardContent>
      </Card>

      <Card className="border-border/60">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Active Dataset Snapshot
          </CardTitle>
          <Database className="size-4 text-blue-500" />
        </CardHeader>
        <CardContent>
          <div className="text-sm font-semibold truncate font-mono mt-1 text-foreground" title={metrics?.active_dataset_version || 'v1.0-default'}>
            {metrics?.active_dataset_version || 'v1.0-default'}
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Local evaluation / benchmark version
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
