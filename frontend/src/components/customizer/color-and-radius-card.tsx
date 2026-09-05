'use client'

import { useCustomizer } from '@/contexts/customizer-context'
import { PresetSelect } from '@/components/customizer/preset-select'
import { RadiusPicker } from '@/components/customizer/radius-picker'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'

export function ColorAndRadiusCard() {
  const { presetId, radius, selectPreset, selectRadius } = useCustomizer()

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Color & Radius</CardTitle>
        <CardDescription>Pick an accent color and corner roundness.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          <div className="text-sm font-medium">Theme</div>
          <PresetSelect value={presetId} onChange={selectPreset} />
        </div>

        <Separator />

        <div className="space-y-3">
          <div className="text-sm font-medium">Radius</div>
          <RadiusPicker value={radius} onChange={selectRadius} />
        </div>
      </CardContent>
    </Card>
  )
}
