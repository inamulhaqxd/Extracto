'use client'

import { createContext, useContext, useState, type ReactNode } from 'react'
import { useThemeManager } from '@/hooks/customizer/use-theme-manager'
import {
  loadCustomizerState,
  saveCustomizerState,
  clearCustomizerState,
} from '@/hooks/customizer/use-customizer-storage'
import { useSidebarConfig } from '@/contexts/sidebar-config-context'
import type { ThemeVars } from '@/lib/theme-presets'

interface CustomizerContextValue {
  presetId: string
  radius: string
  brandColors: Record<string, string>
  selectPreset: (id: string) => void
  selectRadius: (value: string) => void
  changeBrandColor: (cssVar: string, value: string) => void
  importTheme: (vars: ThemeVars) => void
  reset: () => void
}

const CustomizerContext = createContext<CustomizerContextValue | null>(null)

export function CustomizerProvider({ children }: { children: ReactNode }) {
  const { isDarkMode, brandColors, setBrandColors, applyPreset, applyImportedVars, applyRadius, setBrandColor, resetAll } =
    useThemeManager()
  const { resetConfig } = useSidebarConfig()

  const [presetId, setPresetId] = useState(() => loadCustomizerState()?.presetId ?? 'default')
  const [radius, setRadius] = useState(() => loadCustomizerState()?.radius ?? '10px')

  function selectPreset(id: string) {
    setPresetId(id)
    applyPreset(id, isDarkMode)
    saveCustomizerState({ presetId: id })
  }

  function selectRadius(value: string) {
    setRadius(value)
    applyRadius(value)
    saveCustomizerState({ radius: value })
  }

  function changeBrandColor(cssVar: string, value: string) {
    setBrandColor(cssVar, value)
    saveCustomizerState({ brandColors: { ...brandColors, [cssVar.replace('--', '')]: value } })
  }

  function importTheme(vars: ThemeVars) {
    applyImportedVars(vars)
    saveCustomizerState({ brandColors: { ...brandColors, ...vars } })
  }

  function reset() {
    setPresetId('default')
    setRadius('10px')
    setBrandColors({})
    resetAll()
    resetConfig()
    clearCustomizerState()
  }

  return (
    <CustomizerContext.Provider
      value={{
        presetId,
        radius,
        brandColors,
        selectPreset,
        selectRadius,
        changeBrandColor,
        importTheme,
        reset,
      }}
    >
      {children}
    </CustomizerContext.Provider>
  )
}

export function useCustomizer() {
  const context = useContext(CustomizerContext)
  if (!context) {
    throw new Error('useCustomizer must be used within a CustomizerProvider')
  }
  return context
}
