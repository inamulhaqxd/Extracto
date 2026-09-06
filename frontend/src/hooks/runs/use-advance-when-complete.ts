'use client'

import { useEffect, useRef } from 'react'
import type { RunStatus } from '@/types'

const ADVANCE_DELAY_MS = 600

export function useAdvanceWhenComplete(status: RunStatus, onComplete: () => void) {
  const wasCompletedOnMount = useRef(status === 'completed')

  useEffect(() => {
    if (status !== 'completed' || wasCompletedOnMount.current) return

    const timer = setTimeout(onComplete, ADVANCE_DELAY_MS)
    return () => clearTimeout(timer)
  }, [status, onComplete])
}
