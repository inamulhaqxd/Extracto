import { ModeCard } from '@/components/customizer/mode-card'
import { ColorAndRadiusCard } from '@/components/customizer/color-and-radius-card'
import { AdvancedThemeCard } from '@/components/customizer/advanced-theme-card'
import { SidebarLayoutCard } from '@/components/customizer/sidebar-layout-card'

export default function AppearanceSettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Appearance</h2>
        <p className="text-sm text-muted-foreground">
          Choose how TenderFlow looks on this device.
        </p>
      </div>

      <div className="space-y-6">
        <ModeCard />
        <ColorAndRadiusCard />
        <AdvancedThemeCard />
        <SidebarLayoutCard />
      </div>
    </div>
  )
}
