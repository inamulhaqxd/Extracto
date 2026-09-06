'use client'

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { ColorInput } from '@/components/customizer/color-input'

const BASE_COLORS = [
  { name: 'Primary', cssVar: '--primary' },
  { name: 'Primary Foreground', cssVar: '--primary-foreground' },
  { name: 'Secondary', cssVar: '--secondary' },
  { name: 'Secondary Foreground', cssVar: '--secondary-foreground' },
  { name: 'Accent', cssVar: '--accent' },
  { name: 'Accent Foreground', cssVar: '--accent-foreground' },
  { name: 'Muted', cssVar: '--muted' },
  { name: 'Muted Foreground', cssVar: '--muted-foreground' },
]

export function BrandColorsSection({
  values,
  onChange,
}: {
  values: Record<string, string>
  onChange: (cssVar: string, value: string) => void
}) {
  return (
    <Accordion>
      <AccordionItem id="brand-colors" className="rounded-control border border-border">
        <AccordionTrigger className="px-4">Brand Colors</AccordionTrigger>
        <AccordionContent className="space-y-3 border-t border-border bg-muted/20 px-4">
          {BASE_COLORS.map((color) => (
            <ColorInput
              key={color.cssVar}
              label={color.name}
              cssVar={color.cssVar}
              value={values[color.cssVar.replace('--', '')] ?? ''}
              onChange={onChange}
            />
          ))}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
