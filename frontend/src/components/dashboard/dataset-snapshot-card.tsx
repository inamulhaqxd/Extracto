'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Download, Cpu, ShieldCheck, HelpCircle, HardDrive } from 'lucide-react'
import type { QualityMetricsResponse } from '@/lib/api/runs'

interface DatasetSnapshotCardProps {
  metrics: QualityMetricsResponse | null
  isExporting: boolean
  onExport: () => void
}

export function DatasetSnapshotCard({
  metrics,
  isExporting,
  onExport,
}: DatasetSnapshotCardProps) {
  const layer = metrics?.layer_breakdown || {
    deterministic_rules: 0,
    verified_llm: 0,
    fallback: 0,
  }
  const totalLayers =
    (layer.deterministic_rules || 0) +
    (layer.verified_llm || 0) +
    (layer.fallback || 0)

  const rulePct = totalLayers ? Math.round((layer.deterministic_rules / totalLayers) * 100) : 0
  const llmPct = totalLayers ? Math.round((layer.verified_llm / totalLayers) * 100) : 0
  const fallbackPct = totalLayers ? Math.round((layer.fallback / totalLayers) * 100) : 0

  const fingerprints = metrics?.fingerprint_groups || []

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {/* Pipeline Resolving Layer Distribution */}
      <Card className="border-border/60">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Cpu className="size-4 text-primary" />
            Resolving Layer Distribution
          </CardTitle>
          <CardDescription>
            Proportion of decisions resolved by deterministic rules vs verified local LLM
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-medium">
              <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                <ShieldCheck className="size-3.5" />
                Deterministic Rules ({rulePct}%)
              </span>
              <span>{layer.deterministic_rules} items</span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                style={{ width: `${rulePct}%` }}
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-medium">
              <span className="flex items-center gap-1.5 text-blue-600 dark:text-blue-400">
                <Cpu className="size-3.5" />
                Verified Local LLM ({llmPct}%)
              </span>
              <span>{layer.verified_llm} items</span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-300"
                style={{ width: `${llmPct}%` }}
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-medium">
              <span className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                <HelpCircle className="size-3.5" />
                Fallback / Rule Matches ({fallbackPct}%)
              </span>
              <span>{layer.fallback} items</span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-amber-500 rounded-full transition-all duration-300"
                style={{ width: `${fallbackPct}%` }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Dynamic Document Fingerprint Groups & Export Action */}
      <Card className="border-border/60 flex flex-col justify-between">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <HardDrive className="size-4 text-primary" />
            Document Fingerprint Clusters
          </CardTitle>
          <CardDescription>
            Dynamic accuracy metrics for repeated RFP document and template pairings (min. 2 samples)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 flex-1">
          {fingerprints.length === 0 ? (
            <div className="py-6 text-center text-xs text-muted-foreground">
              No clusters with 2+ processed runs yet. As you process repeated document types,
              calibration statistics will populate here automatically.
            </div>
          ) : (
            <div className="space-y-2.5 max-h-40 overflow-y-auto pr-1">
              {fingerprints.map((fg) => (
                <div
                  key={fg.fingerprint}
                  className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/30 p-2 text-xs"
                >
                  <div className="truncate max-w-[220px]" title={fg.label}>
                    <span className="font-medium text-foreground">{fg.label}</span>
                    <span className="text-muted-foreground ml-1">({fg.sample_count} samples)</span>
                  </div>
                  <Badge variant="outline" className="font-mono text-xs">
                    {Math.round(fg.accuracy * 100)}% accuracy
                  </Badge>
                </div>
              ))}
            </div>
          )}

          <div className="pt-2 border-t border-border/40 flex items-center justify-between">
            <div className="text-xs text-muted-foreground">
              Active: <code className="font-mono font-medium">{metrics?.active_dataset_version || 'v1.0-default'}</code>
            </div>
            <Button
              size="sm"
              variant="outline"
              onPress={onExport}
              isDisabled={isExporting}
              className="gap-1.5 text-xs"
            >
              <Download className="size-3.5" />
              {isExporting ? 'Exporting...' : 'Export Dataset Snapshot'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
