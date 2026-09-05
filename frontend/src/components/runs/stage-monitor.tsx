'use client'

import { CheckCircle2, ChevronLeft, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ProcessingRun } from '@/types'
import { RUN_STATUS_BADGE_VARIANT, RUN_STATUS_LABEL } from '@/lib/run-status'
import { useAdvanceWhenComplete } from '@/hooks/runs/use-advance-when-complete'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

export function StageMonitor({
  run,
  onComplete,
  onBack,
}: {
  run: ProcessingRun
  onComplete: () => void
  onBack: () => void
}) {
  useAdvanceWhenComplete(run.status, onComplete)

  const isCompleted = run.status === 'completed'

  return (
    <div className="space-y-8">
      <div className="space-y-3" aria-live="polite">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-2 text-lg font-semibold">
            {isCompleted && <CheckCircle2 aria-hidden="true" className="size-5 text-success" />}
            {run.current_step ?? 'Waiting to start…'}
          </span>
          <Badge variant={RUN_STATUS_BADGE_VARIANT[run.status]}>{RUN_STATUS_LABEL[run.status]}</Badge>
        </div>

        <div className="space-y-2">
          <div
            role="progressbar"
            aria-valuenow={Math.round(run.progress)}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-1.5 w-full overflow-hidden rounded-pill bg-muted"
          >
            <div
              className={cn('h-full rounded-pill transition-all', isCompleted ? 'bg-success' : 'bg-primary')}
              style={{ width: `${run.progress}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              {run.status === 'processing' && (
                <Loader2 aria-hidden="true" className="size-3 animate-spin" />
              )}
              {run.status === 'processing' ? 'Processing' : 'Progress'}
            </span>
            <span className="font-medium tabular-nums">{Math.round(run.progress)}%</span>
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <div className="text-xs text-muted-foreground">Reference PDF</div>
          <div className="truncate text-sm font-medium">{run.pdf_filename}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Excel Template</div>
          <div className="truncate text-sm font-medium">{run.excel_filename}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Model</div>
          <div className="truncate text-sm font-medium">{run.model}</div>
        </div>
      </div>

      <div className="flex justify-start">
        <Button variant="secondary" size="lg" onPress={onBack}>
          <ChevronLeft aria-hidden="true" />
          Back
        </Button>
      </div>
    </div>
  )
}
