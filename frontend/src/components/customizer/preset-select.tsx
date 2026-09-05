'use client'

import { THEME_PRESETS } from '@/lib/theme-presets'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

function Swatch({ colors }: { colors: [string, string, string, string] }) {
  return (
    <div className="flex gap-1">
      {colors.map((color, i) => (
        <span
          key={i}
          className="size-3 rounded-pill border border-border/20"
          style={{ backgroundColor: color }}
        />
      ))}
    </div>
  )
}

export function PresetSelect({
  value,
  onChange,
}: {
  value: string
  onChange: (id: string) => void
}) {
  return (
    <Select value={value} onChange={(key) => key && onChange(String(key))} className="w-full">
      <SelectTrigger>
        <SelectValue />
      </SelectTrigger>
      <SelectContent className="max-h-60">
        {THEME_PRESETS.map((preset) => (
          <SelectItem key={preset.id} id={preset.id}>
            <div className="flex items-center gap-2">
              <Swatch colors={preset.swatch} />
              <span>{preset.name}</span>
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
