'use client'

import { useApplyStoredCustomizer } from '@/hooks/customizer/use-apply-stored-customizer'

export function CustomizerBootstrap() {
  useApplyStoredCustomizer()
  return null
}
