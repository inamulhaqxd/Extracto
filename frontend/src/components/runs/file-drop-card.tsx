'use client'

import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Label } from '@/components/ui/label'

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(0)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function FileDropCard({
  label,
  hint,
  icon: Icon,
  accept,
  file,
  onSelect,
}: {
  label: string
  hint: string
  icon: LucideIcon
  accept: string
  file: File | null
  onSelect: (file: File | null) => void
}) {
  const inputId = `file-${label.replace(/\s+/g, '-').toLowerCase()}`

  return (
    <Label
      htmlFor={inputId}
      className={cn(
        'group/dropzone flex cursor-pointer flex-col items-center justify-center gap-3 rounded-surface border border-dashed p-8 text-center transition-colors',
        file ? 'border-primary/50 bg-primary/5' : 'border-border hover:border-primary/40 hover:bg-muted/50'
      )}
    >
      <span
        className={cn(
          'flex size-11 items-center justify-center rounded-control transition-colors',
          file
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted text-muted-foreground group-hover/dropzone:text-foreground'
        )}
      >
        <Icon aria-hidden="true" className="size-5" />
      </span>
      <div className="space-y-1">
        <div className="text-sm font-medium">{label}</div>
        <div className="text-xs text-muted-foreground">
          {file ? formatFileSize(file.size) : hint}
        </div>
        {file && <div className="text-xs font-medium">{file.name}</div>}
      </div>
      <input
        id={inputId}
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(e) => onSelect(e.target.files?.[0] ?? null)}
      />
    </Label>
  )
}
