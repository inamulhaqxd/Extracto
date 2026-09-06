'use client'

import { cn } from '@/lib/utils'
import { useSidebarConfig, type SidebarLayoutConfig } from '@/contexts/sidebar-config-context'
import { saveCustomizerState } from '@/hooks/customizer/use-customizer-storage'

const VARIANTS: { name: string; value: SidebarLayoutConfig['variant']; description: string }[] = [
  { name: 'Default', value: 'sidebar', description: 'Standard sidebar layout' },
  { name: 'Floating', value: 'floating', description: 'Floating sidebar with border' },
  { name: 'Inset', value: 'inset', description: 'Inset sidebar with rounded corners' },
]

const COLLAPSIBLE_OPTIONS: {
  name: string
  value: SidebarLayoutConfig['collapsible']
  description: string
}[] = [
  { name: 'Off Canvas', value: 'offcanvas', description: 'Slides out of view' },
  { name: 'Icon', value: 'icon', description: 'Collapses to icon only' },
  { name: 'None', value: 'none', description: 'Always visible' },
]

function OptionCard({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        'rounded-control border p-3 text-center text-xs font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
        active ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/40'
      )}
    >
      {children}
    </button>
  )
}

export function SidebarLayoutTab() {
  const { config, updateConfig } = useSidebarConfig()

  function change(next: Partial<SidebarLayoutConfig>) {
    updateConfig(next)
    saveCustomizerState({ sidebar: { ...config, ...next } })
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="text-sm font-medium">Variant</div>
        <div className="grid grid-cols-3 gap-2">
          {VARIANTS.map((variant) => (
            <OptionCard
              key={variant.value}
              active={config.variant === variant.value}
              onClick={() => change({ variant: variant.value })}
            >
              {variant.name}
            </OptionCard>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {VARIANTS.find((v) => v.value === config.variant)?.description}
        </p>
      </div>

      <div className="space-y-3">
        <div className="text-sm font-medium">Collapsible Mode</div>
        <div className="grid grid-cols-3 gap-2">
          {COLLAPSIBLE_OPTIONS.map((option) => (
            <OptionCard
              key={option.value}
              active={config.collapsible === option.value}
              onClick={() => change({ collapsible: option.value })}
            >
              {option.name}
            </OptionCard>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {COLLAPSIBLE_OPTIONS.find((o) => o.value === config.collapsible)?.description}
        </p>
      </div>
    </div>
  )
}
