'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { cn } from '@/lib/utils'
import { settingsTabs } from '@/config/settings'

export function SettingsNavTabs() {
  const pathname = usePathname()

  return (
    <div className="flex gap-1 overflow-x-auto rounded-control bg-muted p-1">
      {settingsTabs.map((tab) => {
        const isActive = pathname === tab.href
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              'flex flex-1 items-center justify-center gap-1.5 rounded-control px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors',
              isActive
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <tab.icon className="size-4" aria-hidden="true" />
            {tab.title}
          </Link>
        )
      })}
    </div>
  )
}
