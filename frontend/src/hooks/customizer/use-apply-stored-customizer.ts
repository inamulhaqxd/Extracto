'use client'

import { useEffect } from 'react'
import { useTheme } from 'next-themes'
import { loadCustomizerState } from '@/hooks/customizer/use-customizer-storage'
import { useSidebarConfig } from '@/contexts/sidebar-config-context'
import { THEME_PRESETS } from '@/lib/theme-presets'

export function useApplyStoredCustomizer() {
  const { theme } = useTheme()
  const { updateConfig } = useSidebarConfig()

  useEffect(() => {
    const stored = loadCustomizerState()
    if (!stored) return

    if (stored.sidebar) {
      updateConfig(stored.sidebar)
    }

    if (stored.radius) {
      document.documentElement.style.setProperty('--radius', stored.radius)
    }

    const isDark =
      theme === 'dark' ||
      (theme === 'system' &&
        typeof window !== 'undefined' &&
        window.matchMedia('(prefers-color-scheme: dark)').matches)

    if (stored.presetId) {
      const preset = THEME_PRESETS.find((p) => p.id === stored.presetId)
      if (preset) {
        const vars = isDark ? preset.dark : preset.light
        Object.entries(vars).forEach(([key, value]) =>
          document.documentElement.style.setProperty(`--${key}`, value)
        )
      }
    }

    if (stored.brandColors) {
      Object.entries(stored.brandColors).forEach(([key, value]) =>
        document.documentElement.style.setProperty(`--${key}`, value)
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
