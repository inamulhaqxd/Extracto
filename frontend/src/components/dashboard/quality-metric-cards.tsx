'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CheckCircle2, AlertTriangle, FileText, Layers } from 'lucide-react'
import type { QualityMetricsResponse } from '@/lib/api/runs'

interface QualityMetricCardsProps {
  metrics: QualityMetricsResponse | null
  totalRuns?: number
  loading: boolean
}

export function QualityMetricCards({ metrics, totalRuns, loading }: QualityMetricCardsProps) {
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

  const runsCount = metrics?.total_runs ?? totalRuns ?? 0

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card className="border-border/60">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Total Runs
          </CardTitle>
          <FileText className="size-4 text-blue-500" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold tracking-tight">
            {runsCount}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {metrics?.reviewed_runs ?? 0} reviewed across all documents
          </p>
        </CardContent>
      </Card>

      <Card className="border-border/60">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Extraction Accuracy
          </CardTitle>
          <CheckCircle2 className="size-4 text-emerald-500" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold tracking-tight">
            {metrics ? `${accuracyPct}%` : 'N/A'}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Verified ground truth match
          </p>
        </CardContent>
      </Card>

      <Card className="border-border/60">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Specs Extracted
          </CardTitle>
          <Layers className="size-4 text-primary" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold tracking-tight">
            {metrics?.total_reviewed_examples ?? 0}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Total RFP specifications evaluated
          </p>
        </CardContent>
      </Card>

      <Card className="border-border/60">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Needs Review
          </CardTitle>
          <AlertTriangle className="size-4 text-amber-500" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold tracking-tight">
            {metrics?.low_confidence_failures ?? 0}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Confidence &lt; 70% or flagged for review
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
