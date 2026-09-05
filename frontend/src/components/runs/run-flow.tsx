'use client'

import { useCallback } from 'react'
import { useRunPipeline } from '@/hooks/runs/use-run-pipeline'
import { useRunStage } from '@/hooks/runs/use-run-stage'
import { RunStepper } from '@/components/runs/run-stepper'
import { StageUpload } from '@/components/runs/stage-upload'
import { StageMonitor } from '@/components/runs/stage-monitor'
import { StageReview } from '@/components/runs/stage-review'
import { StageExport } from '@/components/runs/stage-export'

export function RunFlow() {
  const { run, startWithFiles, reset, decide } = useRunPipeline()
  const { stage, goToUpload, goToMonitor, goToReview, goToExport } = useRunStage()

  const handleStart = useCallback((pdfFile: File, excelFile: File, modelTag?: string | null) => {
    startWithFiles(pdfFile, excelFile, modelTag)
    goToMonitor()
  }, [startWithFiles, goToMonitor])

  const handleBackToUpload = useCallback(() => {
    reset()
    goToUpload()
  }, [reset, goToUpload])

  return (
    <div className="space-y-8">
      <RunStepper current={stage} />

      {stage === 'upload' && <StageUpload onStart={handleStart} />}
      {stage === 'monitor' && run && (
        <StageMonitor run={run} onComplete={goToReview} onBack={handleBackToUpload} />
      )}
      {stage === 'review' && run && (
        <StageReview run={run} onDecide={decide} onBack={handleBackToUpload} onContinue={goToExport} />
      )}
      {stage === 'export' && run && <StageExport run={run} />}
    </div>
  )
}
