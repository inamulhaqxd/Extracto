'use client'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function ColorInput({
  label,
  cssVar,
  value,
  onChange,
}: {
  label: string
  cssVar: string
  value: string
  onChange: (cssVar: string, value: string) => void
}) {
  const inputId = `color-${cssVar}`

  return (
    <div className="space-y-1.5">
      <Label htmlFor={inputId} className="text-xs font-medium">
        {label}
      </Label>
      <div className="flex items-center gap-2">
        <input
          type="color"
          id={inputId}
          value={value.startsWith('#') ? value : '#000000'}
          onChange={(e) => onChange(cssVar, e.target.value)}
          className="size-8 shrink-0 cursor-pointer rounded-control border border-input bg-transparent p-0.5"
          aria-label={`${label} color swatch`}
        />
        <Input
          value={value}
          onChange={(e) => onChange(cssVar, e.target.value)}
          placeholder={cssVar}
          className="h-8 flex-1 text-xs"
        />
      </div>
    </div>
  )
}
