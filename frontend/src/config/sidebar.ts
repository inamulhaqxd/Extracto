import { FileText, LayoutDashboard, Settings, type LucideIcon } from 'lucide-react'

export interface NavItem {
  title: string
  url: string
  icon: LucideIcon
}

export interface NavGroup {
  title: string
  items: NavItem[]
}

export const sidebarData: { navGroups: NavGroup[] } = {
  navGroups: [
    {
      title: 'Overview',
      items: [
        { title: 'Dashboard', url: '/dashboard', icon: LayoutDashboard },
        { title: 'Specifications', url: '/rfp', icon: FileText },
      ],
    },
    {
      title: 'Preferences',
      items: [{ title: 'Settings', url: '/settings', icon: Settings }],
    },
  ],
}
