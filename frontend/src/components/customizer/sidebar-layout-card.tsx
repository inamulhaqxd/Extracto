import { SidebarLayoutTab } from '@/components/customizer/sidebar-layout-tab'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function SidebarLayoutCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Sidebar</CardTitle>
        <CardDescription>How the navigation sidebar looks and collapses.</CardDescription>
      </CardHeader>
      <CardContent>
        <SidebarLayoutTab />
      </CardContent>
    </Card>
  )
}
