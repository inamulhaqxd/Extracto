'use client'

import { ChevronLeft } from 'lucide-react'
import type { DecisionStatus, ProcessingRun } from '@/types'
import { confidenceTone } from '@/lib/confidence'
import { useReviewSummary } from '@/hooks/runs/use-review-summary'
import { useSortedDecisions } from '@/hooks/runs/use-sorted-decisions'
import { RequirementTableRow } from '@/components/runs/requirement-table-row'
import { SummaryCard } from '@/components/runs/summary-card'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableHead, TableHeader } from '@/components/ui/table'

export function StageReview({
  run,
  onDecide,
  onBack,
  onContinue,
}: {
  run: ProcessingRun
  onDecide: (id: string, status: DecisionStatus, overrideValue?: string) => void
  onBack: () => void
  onContinue: () => void
}) {
  const summary = useReviewSummary(run.decisions)
  const sortedDecisions = useSortedDecisions(run.decisions)

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-4" aria-live="polite">
        <SummaryCard label="Requirements" value={summary.total} />
        <SummaryCard
          label="Avg. Confidence"
          value={`${Math.round(summary.averageConfidence * 100)}%`}
          tone={confidenceTone(summary.averageConfidence)}
        />
        <SummaryCard label="Needs a Second Look" value={summary.needsAttention} tone="warning" />
        <SummaryCard label="Still Pending" value={summary.pending} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Extracted requirements</CardTitle>
          <CardDescription>
            Sorted from lowest to highest confidence. Approve, reject, or override any item —
            unreviewed items export as extracted.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table aria-label="Extracted requirements">
            <TableHeader>
              <TableHead isRowHeader>Requirement</TableHead>
              <TableHead className="text-center">Confidence</TableHead>
              <TableHead className="text-center">Status</TableHead>
              <TableHead className="text-center">Actions</TableHead>
            </TableHeader>
            <TableBody>
              {sortedDecisions.map((decision) => (
                <RequirementTableRow key={decision.id} decision={decision} onDecide={onDecide} />
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button variant="secondary" size="lg" onPress={onBack}>
          <ChevronLeft aria-hidden="true" />
          Back
        </Button>
        <Button size="lg" onPress={onContinue}>
          Continue to Export
        </Button>
      </div>
    </div>
  )
}
