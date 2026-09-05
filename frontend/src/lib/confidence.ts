export const LOW_CONFIDENCE_THRESHOLD = 0.7

export function confidenceColor(confidence: number) {
  if (confidence >= 0.85) return 'text-success'
  if (confidence >= LOW_CONFIDENCE_THRESHOLD) return 'text-warning'
  return 'text-destructive'
}

export function confidenceLabel(confidence: number) {
  if (confidence >= 0.85) return 'High confidence'
  if (confidence >= LOW_CONFIDENCE_THRESHOLD) return 'Medium confidence'
  return 'Low confidence'
}

export function isLowConfidence(confidence: number) {
  return confidence < LOW_CONFIDENCE_THRESHOLD
}

export function confidenceTone(confidence: number): 'success' | 'warning' | 'destructive' {
  if (confidence >= 0.85) return 'success'
  if (confidence >= LOW_CONFIDENCE_THRESHOLD) return 'warning'
  return 'destructive'
}
