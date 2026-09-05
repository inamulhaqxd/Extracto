'use client'

import { CheckCircle2, Download, FileSpreadsheet } from 'lucide-react'
import type { ProcessingRun } from '@/types'
import { useDecisionCounts } from '@/hooks/runs/use-decision-counts'
import { SummaryCard } from '@/components/runs/summary-card'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from '@/components/ui/item'

export function StageExport({ run }: { run: ProcessingRun }) {
  const counts = useDecisionCounts(run.decisions)

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-pill bg-success/10 text-success">
            <CheckCircle2 aria-hidden="true" className="size-5" />
          </span>
          <div>
            <div className="font-medium">Compliance analysis complete</div>
            <div className="text-sm text-muted-foreground">
              {run.decisions.length} requirements extracted from {run.pdf_filename}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-4">
        <SummaryCard label="Approved" value={counts.approved} tone="success" />
        <SummaryCard label="Overridden" value={counts.overridden} tone="warning" />
        <SummaryCard label="Rejected" value={counts.rejected} tone="destructive" />
        <SummaryCard label="Exported as Extracted" value={counts.pending} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Export</CardTitle>
          <CardDescription>Download the populated compliance workbook</CardDescription>
        </CardHeader>
        <CardContent>
          <Item variant="outline">
            <ItemMedia variant="icon">
              <FileSpreadsheet aria-hidden="true" />
            </ItemMedia>
            <ItemContent>
              <ItemTitle>{run.excel_filename}</ItemTitle>
              <ItemDescription>Compliance Summary included</ItemDescription>
            </ItemContent>
            <ItemActions>
              <Button size="sm">
                <Download aria-hidden="true" />
                Download
              </Button>
            </ItemActions>
          </Item>
        </CardContent>
      </Card>
    </div>
  )
}
