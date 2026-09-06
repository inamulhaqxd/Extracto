import type { DecisionStatus } from '@/types'
import { Badge } from '@/components/ui/badge'

const STATUS_BADGE: Record<
  DecisionStatus,
  { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }
> = {
  pending: { label: 'Pending', variant: 'outline' },
  approved: { label: 'Approved', variant: 'default' },
  rejected: { label: 'Rejected', variant: 'destructive' },
  overridden: { label: 'Overridden', variant: 'secondary' },
}

export function DecisionBadge({ status }: { status: DecisionStatus }) {
  const badge = STATUS_BADGE[status]
  return <Badge variant={badge.variant}>{badge.label}</Badge>
}
