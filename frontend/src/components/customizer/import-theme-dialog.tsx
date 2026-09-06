'use client'

import { useImportThemeForm } from '@/hooks/customizer/use-import-theme-form'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import type { ThemeVars } from '@/lib/theme-presets'

export function ImportThemeDialog({
  open,
  onOpenChange,
  onImport,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onImport: (vars: ThemeVars) => void
}) {
  const { text, setText, submit } = useImportThemeForm(onImport, () => onOpenChange(false))

  return (
    <Dialog isOpen={open} onOpenChange={onOpenChange} className="sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>Import Custom CSS</DialogTitle>
        <DialogDescription>
          Paste CSS with <code>:root</code> and <code>.dark</code> sections containing variables
          like <code>--primary</code>, <code>--background</code>, etc.
        </DialogDescription>
      </DialogHeader>

      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={':root {\n  --primary: oklch(0.5 0.2 260);\n}\n.dark {\n  --primary: oklch(0.7 0.2 260);\n}'}
        className="min-h-60 resize-none font-mono text-xs"
      />

      <DialogFooter>
        <Button variant="outline" onPress={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button onPress={submit} isDisabled={!text.trim()}>
          Import Theme
        </Button>
      </DialogFooter>
    </Dialog>
  )
}
