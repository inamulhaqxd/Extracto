import { Card, CardContent } from '@/components/ui/card'

const TONE_CLASS = {
  neutral: 'text-foreground',
  success: 'text-success',
  destructive: 'text-destructive',
  warning: 'text-warning',
} as const

export function SummaryCard({
  label,
  value,
  tone = 'neutral',
}: {
  label: string
  value: number | string
  tone?: keyof typeof TONE_CLASS
}) {
  return (
    <Card>
      <CardContent className="space-y-1">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className={`text-xl font-semibold tabular-nums ${TONE_CLASS[tone]}`}>{value}</div>
      </CardContent>
    </Card>
  )
}
