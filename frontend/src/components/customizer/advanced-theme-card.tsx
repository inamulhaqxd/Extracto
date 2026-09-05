'use client'

import { useCustomizer } from '@/contexts/customizer-context'
import { useImportDialog } from '@/hooks/customizer/use-import-dialog'
import { BrandColorsSection } from '@/components/customizer/brand-colors-section'
import { ImportThemeDialog } from '@/components/customizer/import-theme-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function AdvancedThemeCard() {
  const { brandColors, changeBrandColor, importTheme } = useCustomizer()
  const { importOpen, setImportOpen } = useImportDialog()

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Advanced</CardTitle>
        <CardDescription>Import a custom CSS theme or fine-tune individual colors.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button variant="outline" onPress={() => setImportOpen(true)} className="w-full">
          Import Theme
        </Button>

        <BrandColorsSection values={brandColors} onChange={changeBrandColor} />
      </CardContent>

      <ImportThemeDialog open={importOpen} onOpenChange={setImportOpen} onImport={importTheme} />
    </Card>
  )
}
