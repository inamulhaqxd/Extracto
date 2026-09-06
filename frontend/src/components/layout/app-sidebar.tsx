'use client'

import { FileText } from 'lucide-react'
import Link from 'next/link'
import { sidebarData } from '@/config/sidebar'
import { useCurrentUser } from '@/hooks/use-current-user'
import { useSidebarConfig } from '@/contexts/sidebar-config-context'
import { NavGroup } from '@/components/layout/nav-group'
import { NavUser } from '@/components/layout/nav-user'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from '@/components/ui/sidebar'

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const user = useCurrentUser()
  const { config } = useSidebarConfig()

  return (
    <Sidebar variant={config.variant} collapsible={config.collapsible} {...props}>
      <SidebarHeader>
        <Link
          href="/dashboard"
          className="flex items-center gap-2.5 rounded-control p-2 group-data-[collapsible=icon]:size-9 group-data-[collapsible=icon]:p-0"
        >
          <span className="flex size-8 shrink-0 items-center justify-center rounded-control bg-primary text-primary-foreground group-data-[collapsible=icon]:size-full">
            <FileText className="size-4 group-data-[collapsible=icon]:size-5" />
          </span>
          <span className="flex flex-col leading-tight group-data-[collapsible=icon]:hidden">
            <span className="text-sm font-semibold tracking-tight">TenderFlow</span>
            <span className="text-xs text-muted-foreground">RFP Automation</span>
          </span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        {sidebarData.navGroups.map((group) => (
          <NavGroup key={group.title} {...group} />
        ))}
      </SidebarContent>
      <SidebarFooter>{user && <NavUser user={user} />}</SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
