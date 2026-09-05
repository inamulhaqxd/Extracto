import { Palette, Sparkles, User, type LucideIcon } from 'lucide-react'

export interface SettingsTab {
  title: string
  href: string
  icon: LucideIcon
}

export const settingsTabs: SettingsTab[] = [
  { title: 'Account', href: '/settings', icon: User },
  { title: 'Appearance', href: '/settings/appearance', icon: Palette },
  { title: 'Compliance', href: '/settings/compliance', icon: Sparkles },
]
