import { SettingsNav } from '@/components/settings/settings-nav'
import { SettingsNavTabs } from '@/components/settings/settings-nav-tabs'
import { SettingsNavMobile } from '@/components/settings/settings-nav-mobile'
import { Separator } from '@/components/ui/separator'

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Manage your account and app preferences.</p>
      </div>

      <Separator />

      <div className="sm:hidden">
        <SettingsNavMobile />
      </div>
      <div className="hidden sm:block lg:hidden">
        <SettingsNavTabs />
      </div>

      <div className="flex gap-8">
        <aside className="hidden w-48 shrink-0 lg:block">
          <SettingsNav />
        </aside>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </div>
  )
}
