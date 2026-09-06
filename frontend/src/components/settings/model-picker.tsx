'use client'

import { AlertTriangle, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useModels } from '@/hooks/use-models'
import { useModelPreference } from '@/hooks/settings/use-model-preference'
import { Skeleton } from '@/components/ui/skeleton'

export function ModelPicker() {
  const { models, defaultModel, loading: modelsLoading } = useModels()
  const { modelTag, setModelTag, loading: prefLoading, saving } = useModelPreference()

  const activeTag = modelTag ?? defaultModel
  const loading = modelsLoading || prefLoading

  if (loading) {
    return (
      <>
        <Skeleton className="h-11 w-full" />
        <Skeleton className="h-11 w-full" />
        <Skeleton className="h-11 w-full" />
      </>
    )
  }

  return (
    <>
      {models.map((option) => {
        const isActive = activeTag === option.tag
        return (
          <button
            key={option.tag}
            type="button"
            aria-pressed={isActive}
            disabled={saving || !option.is_available}
            onClick={() => setModelTag(option.tag)}
            className={cn(
              'flex w-full items-center justify-between gap-3 rounded-control border px-3 py-2.5 text-left text-sm transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50',
              isActive
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/40 hover:bg-muted/50'
            )}
          >
            <div>
              <div className="font-medium">{option.name}</div>
              <div className="text-xs text-muted-foreground">
                {option.ram_usage} RAM · {option.context_length} context
              </div>
              {!option.is_available && (
                <div className="mt-1 font-mono text-xs text-warning">
                  Not installed — run: ollama pull {option.tag}
                </div>
              )}
            </div>
            {isActive && <Check className="size-4 shrink-0 text-primary" aria-hidden="true" />}
          </button>
        )
      })}

      {models.length === 0 && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <AlertTriangle className="size-4" aria-hidden="true" />
          No models available. Check that Ollama is running.
        </div>
      )}
    </>
  )
}
