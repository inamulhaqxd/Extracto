import { ThemePicker } from '@/components/settings/theme-picker'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function ModeCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Mode</CardTitle>
        <CardDescription>Light, dark, or match your system.</CardDescription>
      </CardHeader>
      <CardContent>
        <ThemePicker />
      </CardContent>
    </Card>
  )
}
