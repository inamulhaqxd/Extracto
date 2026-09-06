import type { RunStatus } from '@/types'

export const RUN_STATUS_BADGE_VARIANT: Record<
  RunStatus,
  'default' | 'secondary' | 'destructive' | 'success' | 'warning'
> = {
  pending: 'secondary',
  processing: 'warning',
  completed: 'success',
  cancelled: 'secondary',
  failed: 'destructive',
}

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  completed: 'Completed',
  cancelled: 'Cancelled',
  failed: 'Failed',
}
