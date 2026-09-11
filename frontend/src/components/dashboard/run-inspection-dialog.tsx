'use client'

import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { CheckCircle2, AlertCircle, ArrowRight, Quote } from 'lucide-react'
import type { RunInspectionItem } from '@/lib/api/runs'

interface RunInspectionDialogProps {
  isOpen: boolean
  runId: string | null
  items: RunInspectionItem[]
  loading: boolean
  error: string | null
  onClose: () => void
}

export function RunInspectionDialog({
  isOpen,
  runId,
  items,
  loading,
  error,
  onClose,
}: RunInspectionDialogProps) {
  return (
    <Dialog
      isOpen={isOpen}
      onOpenChange={(open: boolean) => !open && onClose()}
      className="sm:max-w-3xl max-h-[85vh] flex flex-col p-0 overflow-hidden"
    >
      <DialogHeader className="p-6 pb-4 border-b border-border/60">
        <DialogTitle className="text-lg font-semibold flex items-center gap-2">
          Run Quality & Correction Inspection
        </DialogTitle>
        <DialogDescription>
          Comparing local model prediction against reviewer ground-truth (Run: <code className="font-mono text-xs">{runId}</code>)
        </DialogDescription>
      </DialogHeader>

      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {loading ? (
          <div className="space-y-4 py-8 text-center">
            <div className="inline-block size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            <p className="text-sm text-muted-foreground">Loading resolution comparison...</p>
          </div>
        ) : error ? (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-600 dark:text-rose-400">
            {error}
          </div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-sm text-muted-foreground">
            No individual decision records found for this run.
          </div>
        ) : (
          items.map((item, idx) => (
            <div
              key={item.requirement_id || idx}
              className="rounded-xl border border-border/60 bg-card p-4 space-y-3 transition-colors hover:border-border"
            >
              {/* Requirement Header */}
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-muted text-muted-foreground">
                      {item.requirement_id}
                    </span>
                    {item.is_exact_match ? (
                      <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30 gap-1 text-xs">
                        <CheckCircle2 className="size-3" />
                        Exact Match
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="bg-amber-500/10 text-amber-600 border-amber-500/30 gap-1 text-xs">
                        <AlertCircle className="size-3" />
                        Corrected by Reviewer
                      </Badge>
                    )}
                    <span className="text-xs text-muted-foreground">
                      Confidence: {Math.round(item.confidence * 100)}%
                    </span>
                  </div>
                  <p className="text-sm font-medium text-foreground leading-snug">
                    {item.requirement_text}
                  </p>
                </div>
              </div>

              {/* Prediction vs Ground Truth Comparison */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-xs">
                <div className="rounded-lg bg-muted/40 p-3 space-y-1.5 border border-border/40">
                  <div className="font-medium text-muted-foreground uppercase tracking-wider text-[10px]">
                    Model Resolution
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground">Status:</span>
                    <Badge variant="outline" className="text-xs">{item.predicted_status}</Badge>
                  </div>
                  <div className="text-foreground">
                    <span className="font-semibold text-muted-foreground">Extracted:</span>{' '}
                    <span className="font-mono">{item.predicted_value || 'None'}</span>
                  </div>
                </div>

                <div className="rounded-lg bg-primary/5 p-3 space-y-1.5 border border-primary/20">
                  <div className="font-medium text-primary uppercase tracking-wider text-[10px] flex items-center gap-1">
                    <ArrowRight className="size-3" />
                    Reviewer Ground Truth
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground">Status:</span>
                    <Badge variant="outline" className="border-primary/40 text-primary text-xs">
                      {item.corrected_status}
                    </Badge>
                  </div>
                  <div className="text-foreground">
                    <span className="font-semibold text-muted-foreground">Value:</span>{' '}
                    <span className="font-mono font-medium">{item.corrected_value || 'None'}</span>
                  </div>
                </div>
              </div>

              {/* Reviewer Note or Reasoning Snippet */}
              {item.review_notes && (
                <div className="rounded bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 text-xs text-amber-700 dark:text-amber-300">
                  <span className="font-semibold">Reviewer Override Note:</span> {item.review_notes}
                </div>
              )}

              {/* Evidence & Citation Quote */}
              {item.citation && item.citation !== 'None' && (
                <div className="flex items-start gap-1.5 text-xs text-muted-foreground bg-muted/20 rounded px-2.5 py-1.5">
                  <Quote className="size-3.5 shrink-0 text-muted-foreground/60 mt-0.5" />
                  <span className="italic">Citation: {item.citation}</span>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </Dialog>
  )
}
