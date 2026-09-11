'use client'

import { useState } from 'react'
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
  onDecide: (
    id: string,
    status: DecisionStatus,
    overrideValue?: string,
    slotOverrides?: Record<string, string>
  ) => void
}) {
  const { open, setOpen, draft, setDraft, openDialog, closeDialog } = useRequirementOverride(
    decision.override_value ?? decision.extracted_value
  )
  const [slotDrafts, setSlotDrafts] = useState<Record<string, string>>({})
  const [prevOpen, setPrevOpen] = useState(open)

  if (open !== prevOpen) {
    setPrevOpen(open)
    if (open && decision.slots && decision.slots.length > 0) {
      const initial: Record<string, string> = {}
      for (const slot of decision.slots) {
        initial[slot.key] = slot.value
      }
      setSlotDrafts(initial)
    }
  }

  const overrideInputId = `override-${decision.id}`
  const hasMultipleSlots = Boolean(decision.slots && decision.slots.length > 1)

  function saveOverride() {
    if (hasMultipleSlots && decision.slots) {
      const answerSlot =
        decision.slots.find(
          (s) => s.slot_type.toLowerCase() === 'answer' || s.key === 'answer'
        ) ?? decision.slots[0]
      const primaryVal = slotDrafts[answerSlot.key] ?? answerSlot.value
      onDecide(decision.id, 'overridden', primaryVal, slotDrafts)
    } else {
      onDecide(decision.id, 'overridden', draft)
    }
    closeDialog()
  }

  return (
    <TableRow className={isLowConfidence(decision.confidence) ? 'bg-warning/5' : undefined}>
      <TableCell className="max-w-md min-w-0 whitespace-normal">
        <div className="font-medium text-foreground">{decision.requirement}</div>

        {hasMultipleSlots && decision.slots ? (
          <div className="mt-2 space-y-1.5">
            {decision.slots.map((slot) => {
              const displayVal = slot.value
              return (
                <div key={slot.key} className="flex items-baseline gap-2 text-xs">
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded font-mono font-medium bg-muted text-muted-foreground text-[11px] shrink-0">
                    {slot.cell_coordinate ? `${slot.cell_coordinate} (${slot.slot_type})` : slot.slot_type}
                  </span>
                  <span className="text-muted-foreground break-words min-w-0">
                    {displayVal && displayVal !== 'NOT_SPECIFIED' ? (
                      displayVal
                    ) : (
                      <span className="italic text-warning font-mono">NOT_SPECIFIED</span>
                    )}
                  </span>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-muted-foreground text-sm mt-0.5">
            {decision.override_value ?? decision.extracted_value}
          </div>
        )}
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
                Override Slots
              </DropdownMenuItem>
            </DropdownMenu>
          </DropdownMenuTrigger>
        </div>

        <Dialog isOpen={open} onOpenChange={setOpen}>
          <DialogHeader>
            <DialogTitle>Override Column Slots</DialogTitle>
            <DialogDescription>{decision.requirement}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 max-h-[60vh] overflow-y-auto py-1">
            {hasMultipleSlots && decision.slots ? (
              decision.slots.map((slot) => {
                const inputId = `slot-${decision.id}-${slot.key}`
                const label = `${slot.slot_type.toUpperCase()}${
                  slot.cell_coordinate ? ` (Cell ${slot.cell_coordinate})` : ''
                }`
                return (
                  <div key={slot.key} className="space-y-1.5">
                    <Label htmlFor={inputId} className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {label}
                    </Label>
                    <Textarea
                      id={inputId}
                      value={slotDrafts[slot.key] ?? slot.value}
                      onChange={(e) =>
                        setSlotDrafts((prev) => ({
                          ...prev,
                          [slot.key]: e.target.value,
                        }))
                      }
                      rows={slot.slot_type.toLowerCase().includes('remark') ? 3 : 2}
                      placeholder={`Enter ${slot.slot_type} value...`}
                    />
                  </div>
                )
              })
            ) : (
              <div className="space-y-3">
                <div>
                  <div className="text-xs text-muted-foreground">Extracted value</div>
                  <div className="text-sm font-medium">{decision.extracted_value}</div>
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
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onPress={closeDialog}>
              Cancel
            </Button>
            <Button onPress={saveOverride}>Save Overrides</Button>
          </DialogFooter>
        </Dialog>
      </TableCell>
    </TableRow>
  )
}
