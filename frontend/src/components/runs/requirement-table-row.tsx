'use client'

import { Check, MoreVertical, Pencil, X } from 'lucide-react'
import type { DecisionStatus, RequirementDecision } from '@/types'
import { confidenceColor, confidenceLabel, isLowConfidence } from '@/lib/confidence'
import { useRequirementOverride } from '@/hooks/runs/use-requirement-override'
import { DecisionBadge } from '@/components/runs/decision-badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { TableCell, TableRow } from '@/components/ui/table'

export function RequirementTableRow({
  decision,
  onDecide,
}: {
  decision: RequirementDecision
  onDecide: (id: string, status: DecisionStatus, overrideValue?: string) => void
}) {
  const { open, setOpen, draft, setDraft, openDialog, closeDialog } = useRequirementOverride(
    decision.override_value ?? decision.extracted_value
  )
  const overrideInputId = `override-${decision.id}`

  function saveOverride() {
    onDecide(decision.id, 'overridden', draft)
    closeDialog()
  }

  return (
    <TableRow className={isLowConfidence(decision.confidence) ? 'bg-warning/5' : undefined}>
      <TableCell className="max-w-xs min-w-0 whitespace-normal">
        <div className="font-medium">{decision.requirement}</div>
        <div className="text-muted-foreground">
          {decision.override_value ?? decision.extracted_value}
        </div>
      </TableCell>
      <TableCell className="text-center">
        <span className={`font-medium tabular-nums ${confidenceColor(decision.confidence)}`}>
          <span className="sr-only">{confidenceLabel(decision.confidence)}: </span>
          {Math.round(decision.confidence * 100)}%
        </span>
      </TableCell>
      <TableCell className="text-center">
        <DecisionBadge status={decision.status} />
      </TableCell>
      <TableCell>
        <div className="flex justify-center">
          <DropdownMenuTrigger>
            <Button variant="ghost" size="icon-sm" aria-label="Row actions">
              <MoreVertical aria-hidden="true" />
            </Button>
            <DropdownMenu placement="bottom end">
              {decision.status !== 'approved' && (
                <DropdownMenuItem onAction={() => onDecide(decision.id, 'approved')}>
                  <Check aria-hidden="true" />
                  Approve
                </DropdownMenuItem>
              )}
              {decision.status !== 'rejected' && (
                <DropdownMenuItem onAction={() => onDecide(decision.id, 'rejected')}>
                  <X aria-hidden="true" />
                  Reject
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onAction={openDialog}>
                <Pencil aria-hidden="true" />
                Override
              </DropdownMenuItem>
            </DropdownMenu>
          </DropdownMenuTrigger>
        </div>

        <Dialog isOpen={open} onOpenChange={setOpen}>
          <DialogHeader>
            <DialogTitle>Override Value</DialogTitle>
            <DialogDescription>{decision.requirement}</DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div>
              <div className="text-xs text-muted-foreground">Extracted value</div>
              <div className="text-sm">{decision.extracted_value}</div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={overrideInputId}>Override value</Label>
              <Textarea
                id={overrideInputId}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onPress={closeDialog}>
              Cancel
            </Button>
            <Button onPress={saveOverride}>Save Override</Button>
          </DialogFooter>
        </Dialog>
      </TableCell>
    </TableRow>
  )
}
