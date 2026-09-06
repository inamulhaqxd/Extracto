'use client'

import { cn } from '@/lib/utils'
import { RADIUS_PRESETS } from '@/lib/theme-presets'

export function RadiusPicker({
  value,
  onChange,
}: {
  value: string
  onChange: (radius: string) => void
}) {
  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
      {RADIUS_PRESETS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            'flex flex-col items-center gap-2 rounded-control border p-3 text-center text-xs font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
            value === option.value
              ? 'border-primary text-foreground'
              : 'border-border text-muted-foreground hover:border-primary/40'
          )}
        >
          <span
            className="size-6 border-2 border-current"
            style={{ borderRadius: option.value }}
            aria-hidden="true"
          />
          {option.name}
        </button>
      ))}
    </div>
  )
}
