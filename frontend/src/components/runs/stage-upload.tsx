'use client'

import { FileSpreadsheet, FileText, Upload } from 'lucide-react'
import { useUploadForm } from '@/hooks/runs/use-upload-form'
import { useModels } from '@/hooks/use-models'
import { useModelPreference } from '@/hooks/settings/use-model-preference'
import { FileDropCard } from '@/components/runs/file-drop-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export function StageUpload({
  onStart,
}: {
  onStart: (pdfFile: File, excelFile: File, modelTag?: string | null) => void
}) {
  const { pdfFile, setPdfFile, excelFile, setExcelFile, canStart } = useUploadForm()
  const { models, loading: modelsLoading } = useModels()
  const { modelTag, loading: prefLoading } = useModelPreference()

  const activeTag = modelTag ?? models.find((m) => m.is_default)?.tag ?? null
  const modelLabel = models.find((m) => m.tag === activeTag)?.name ?? activeTag ?? 'Default'
  const modelLoading = modelsLoading || prefLoading

  const handleStartClick = () => {
    if (pdfFile && excelFile) {
      onStart(pdfFile, excelFile, activeTag)
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <FileDropCard
          label="Reference PDF"
          hint="PDF, up to 100MB"
          icon={FileText}
          accept="application/pdf"
          file={pdfFile}
          onSelect={setPdfFile}
        />
        <FileDropCard
          label="Excel Template"
          hint="XLSX or XLS, up to 50MB"
          icon={FileSpreadsheet}
          accept=".xlsx,.xls"
          file={excelFile}
          onSelect={setExcelFile}
        />
      </div>

      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          Model
          {modelLoading ? (
            <Skeleton className="h-5 w-24 rounded-pill" />
          ) : (
            <Badge variant="secondary">{modelLabel}</Badge>
          )}
        </div>

        <Button size="lg" onPress={handleStartClick} isDisabled={!canStart} className="w-full sm:w-auto">
          <Upload aria-hidden="true" />
          Start Compliance Analysis
        </Button>
      </div>
    </div>
  )
}
