'use client'

import { ThemeToggler } from '@/components/theme-toggler'
import { useSidebarConfig } from '@/contexts/sidebar-config-context'
import { SidebarTrigger } from '@/components/ui/sidebar'

export function DashboardHeader() {
  const { config } = useSidebarConfig()

  return (
    <header className="sticky top-0 z-50 flex h-14 shrink-0 items-center gap-2 border-b border-border/50 bg-background/80 px-4 backdrop-blur-xl">
      {config.collapsible !== 'none' && <SidebarTrigger className="-ml-1" />}
      <div className="ml-auto flex items-center gap-1">
        <ThemeToggler />
      </div>
    </header>
  )
}
