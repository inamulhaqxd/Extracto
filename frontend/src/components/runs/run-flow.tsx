'use client'

import { useCallback } from 'react'
import { useRunPipeline } from '@/hooks/runs/use-run-pipeline'
import { useRunStage } from '@/hooks/runs/use-run-stage'
import type { RunStageKey } from '@/components/runs/run-stepper'
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

  const isStageAccessible = useCallback(
    (targetStage: RunStageKey): boolean => {
      if (targetStage === 'upload') return true
      if (!run) return false
      if (targetStage === 'monitor') return true
      if (targetStage === 'review' || targetStage === 'export') {
        return Boolean(run.decisions && run.decisions.length > 0) || run.status === 'completed'
      }
      return false
    },
    [run]
  )

  const handleStageSelect = useCallback(
    (targetStage: RunStageKey) => {
      if (targetStage === stage) return
      if (targetStage === 'upload') {
        handleBackToUpload()
      } else if (targetStage === 'monitor' && run) {
        goToMonitor()
      } else if (targetStage === 'review' && run) {
        goToReview()
      } else if (targetStage === 'export' && run) {
        goToExport()
      }
    },
    [stage, run, handleBackToUpload, goToMonitor, goToReview, goToExport]
  )

  return (
    <div className="space-y-8">
      <RunStepper
        current={stage}
        onStageSelect={handleStageSelect}
        isStageAccessible={isStageAccessible}
      />

      {stage === 'upload' && <StageUpload onStart={handleStart} />}
      {stage === 'monitor' && run && (
        <StageMonitor run={run} onComplete={goToReview} onBack={handleBackToUpload} />
      )}
      {stage === 'review' && run && (
        <StageReview run={run} onDecide={decide} onBack={handleBackToUpload} onContinue={goToExport} />
      )}
      {stage === 'export' && run && (
        <StageExport run={run} onBackToReview={goToReview} />
      )}
    </div>
  )
}
