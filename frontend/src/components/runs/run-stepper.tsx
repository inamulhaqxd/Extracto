import { cn } from '@/lib/utils'

export const RUN_STAGES = [
  { key: 'upload', label: 'Upload & Configure' },
  { key: 'monitor', label: 'Processing Monitor' },
  { key: 'review', label: 'Review & Approvals' },
  { key: 'export', label: 'Export & Finalize' },
] as const

export type RunStageKey = (typeof RUN_STAGES)[number]['key']

export function RunStepper({
  current,
  onStageSelect,
  isStageAccessible,
}: {
  current: RunStageKey
  onStageSelect?: (stage: RunStageKey) => void
  isStageAccessible?: (stage: RunStageKey) => boolean
}) {
  const currentIndex = RUN_STAGES.findIndex((s) => s.key === current)

  return (
    <ol className="grid grid-cols-4 gap-3">
      {RUN_STAGES.map((stage, i) => {
        const isDone = i < currentIndex
        const isCurrent = i === currentIndex
        const canClick = Boolean(
          onStageSelect &&
            (isStageAccessible ? isStageAccessible(stage.key) : (isDone || isCurrent))
        )

        return (
          <li
            key={stage.key}
            aria-current={isCurrent ? 'step' : undefined}
            className={cn(
              'flex flex-col gap-2 transition-all',
              canClick &&
                'cursor-pointer group select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm'
            )}
            onClick={() => {
              if (canClick && onStageSelect) {
                onStageSelect(stage.key)
              }
            }}
            onKeyDown={(e) => {
              if (canClick && onStageSelect && (e.key === 'Enter' || e.key === ' ')) {
                e.preventDefault()
                onStageSelect(stage.key)
              }
            }}
            role={canClick ? 'button' : undefined}
            tabIndex={canClick ? 0 : undefined}
            aria-label={`Go to stage: ${stage.label}`}
          >
            <span
              className={cn(
                'text-xs font-medium sm:text-sm transition-colors',
                isCurrent
                  ? 'text-foreground font-semibold'
                  : isDone
                  ? 'text-muted-foreground group-hover:text-foreground'
                  : 'text-muted-foreground/60'
              )}
            >
              {stage.label}
            </span>
            <span
              className={cn(
                'h-1.5 w-full rounded-pill transition-colors',
                isCurrent && 'bg-primary',
                isDone && 'bg-success group-hover:bg-success/80',
                !isDone && !isCurrent && 'bg-muted'
              )}
            />
          </li>
        )
      })}
    </ol>
  )
}
