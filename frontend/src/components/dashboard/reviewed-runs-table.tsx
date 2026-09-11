'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FileText, Eye, CheckCircle2, Clock, AlertCircle, XCircle } from 'lucide-react'
import type { BackendRunResponse } from '@/lib/api/runs'

interface ReviewedRunsTableProps {
  runs: BackendRunResponse[]
  loading: boolean
  onInspect: (runId: string) => void
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'completed':
      return (
        <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30 gap-1 text-xs">
          <CheckCircle2 className="size-3" />
          Completed
        </Badge>
      )
    case 'processing':
      return (
        <Badge variant="outline" className="bg-blue-500/10 text-blue-600 border-blue-500/30 gap-1 text-xs animate-pulse">
          <Clock className="size-3" />
          Processing
        </Badge>
      )
    case 'failed':
      return (
        <Badge variant="outline" className="bg-rose-500/10 text-rose-600 border-rose-500/30 gap-1 text-xs">
          <XCircle className="size-3" />
          Failed
        </Badge>
      )
    case 'cancelled':
      return (
        <Badge variant="outline" className="bg-muted text-muted-foreground gap-1 text-xs">
          Cancelled
        </Badge>
      )
    default:
      return (
        <Badge variant="outline" className="gap-1 text-xs">
          <AlertCircle className="size-3" />
          {status}
        </Badge>
      )
  }
}

function formatDate(dateStr?: string | null) {
  if (!dateStr) return 'N/A'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

export function ReviewedRunsTable({ runs, loading, onInspect }: ReviewedRunsTableProps) {
  return (
    <Card className="border-border/60">
      <CardHeader>
        <CardTitle className="text-base font-semibold">Recent Processing & Reviewed Runs</CardTitle>
        <CardDescription>
          Detailed inspection of model resolutions and human reviewer corrections
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3 py-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 w-full animate-pulse rounded bg-muted/60" />
            ))}
          </div>
        ) : runs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center text-sm text-muted-foreground">
            <FileText className="mb-2 size-8 text-muted-foreground/60" />
            <p className="font-medium">No processing runs found</p>
            <p className="text-xs text-muted-foreground">
              Run an extraction pipeline from the Workspace to see runs here.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table aria-label="Recent processing runs">
              <TableHeader>
                <TableHead isRowHeader>Specification PDF</TableHead>
                <TableHead>Target Excel</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Model</TableHead>
                <TableHead className="text-right">Specs</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableHeader>
              <TableBody>
                {runs.map((run) => (
                  <TableRow key={run.run_id} className="border-border/40">
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <FileText className="size-4 text-primary shrink-0" />
                        <span className="truncate max-w-[180px]" title={run.pdf_filename || 'PDF Document'}>
                          {run.pdf_filename || 'reference.pdf'}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      <span className="truncate max-w-[160px] inline-block" title={run.workbook_filename || 'Excel Template'}>
                        {run.workbook_filename || 'workbook.xlsx'}
                      </span>
                    </TableCell>
                    <TableCell>{getStatusBadge(run.status)}</TableCell>
                    <TableCell>
                      <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                        {run.model_used || 'default'}
                      </code>
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {run.total_requirements}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatDate(run.started_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onPress={() => onInspect(run.run_id)}
                        className="h-8 gap-1 text-xs"
                      >
                        <Eye className="size-3.5" />
                        Inspect
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
