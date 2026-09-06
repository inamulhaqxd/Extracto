import { cn } from '@/lib/utils'

export const RUN_STAGES = [
  { key: 'upload', label: 'Upload & Configure' },
  { key: 'monitor', label: 'Processing Monitor' },
  { key: 'review', label: 'Review & Approvals' },
  { key: 'export', label: 'Export & Finalize' },
] as const

export type RunStageKey = (typeof RUN_STAGES)[number]['key']

export function RunStepper({ current }: { current: RunStageKey }) {
  const currentIndex = RUN_STAGES.findIndex((s) => s.key === current)

  return (
    <ol className="grid grid-cols-4 gap-3">
      {RUN_STAGES.map((stage, i) => {
        const isDone = i < currentIndex
        const isCurrent = i === currentIndex

        return (
          <li key={stage.key} aria-current={isCurrent ? 'step' : undefined} className="flex flex-col gap-2">
            <span
              className={cn(
                'text-xs font-medium sm:text-sm',
                isCurrent ? 'text-foreground' : isDone ? 'text-muted-foreground' : 'text-muted-foreground/60'
              )}
            >
              {stage.label}
            </span>
            <span
              className={cn(
                'h-1.5 w-full rounded-pill',
                isCurrent && 'bg-primary',
                isDone && 'bg-success',
                !isDone && !isCurrent && 'bg-muted'
              )}
            />
          </li>
        )
      })}
    </ol>
  )
}
