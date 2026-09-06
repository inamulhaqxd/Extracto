'use client'

import { useCallback, useMemo, useState } from 'react'
import { useTheme } from 'next-themes'
import { THEME_PRESETS, type ThemeVars } from '@/lib/theme-presets'

const CUSTOMIZABLE_VARS = [
  'background',
  'foreground',
  'card',
  'card-foreground',
  'popover',
  'popover-foreground',
  'primary',
  'primary-foreground',
  'secondary',
  'secondary-foreground',
  'muted',
  'muted-foreground',
  'accent',
  'accent-foreground',
  'destructive',
  'success',
  'warning',
  'border',
  'input',
  'ring',
  'sidebar',
  'sidebar-foreground',
  'sidebar-primary',
  'sidebar-primary-foreground',
  'sidebar-accent',
  'sidebar-accent-foreground',
  'sidebar-border',
  'sidebar-ring',
]

export function useThemeManager() {
  const { theme } = useTheme()
  const [brandColors, setBrandColors] = useState<Record<string, string>>({})

  const isDarkMode = useMemo(() => {
    if (theme === 'dark') return true
    if (theme === 'light') return false
    return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches
  }, [theme])

  const resetVars = useCallback(() => {
    const root = document.documentElement
    CUSTOMIZABLE_VARS.forEach((name) => root.style.removeProperty(`--${name}`))
  }, [])

  const applyVars = useCallback((vars: ThemeVars) => {
    const root = document.documentElement
    Object.entries(vars).forEach(([key, value]) => root.style.setProperty(`--${key}`, value))
    setBrandColors((prev) => ({ ...prev, ...vars }))
  }, [])

  const applyPreset = useCallback(
    (presetId: string, darkMode: boolean) => {
      const preset = THEME_PRESETS.find((p) => p.id === presetId)
      if (!preset) return
      resetVars()
      const vars = darkMode ? preset.dark : preset.light
      applyVars(vars)
    },
    [resetVars, applyVars]
  )

  const applyImportedVars = useCallback(
    (vars: ThemeVars) => {
      applyVars(vars)
    },
    [applyVars]
  )

  const applyRadius = useCallback((radius: string) => {
    document.documentElement.style.setProperty('--radius', radius)
  }, [])

  const setBrandColor = useCallback((cssVar: string, value: string) => {
    document.documentElement.style.setProperty(cssVar, value)
    setBrandColors((prev) => ({ ...prev, [cssVar.replace('--', '')]: value }))
  }, [])

  const resetAll = useCallback(() => {
    resetVars()
    document.documentElement.style.removeProperty('--radius')
    setBrandColors({})
  }, [resetVars])

  return {
    isDarkMode,
    brandColors,
    setBrandColors,
    applyPreset,
    applyImportedVars,
    applyRadius,
    setBrandColor,
    resetAll,
  }
}
