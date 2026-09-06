'use client'

import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

export interface SidebarLayoutConfig {
  variant: 'sidebar' | 'floating' | 'inset'
  collapsible: 'offcanvas' | 'icon' | 'none'
}

export const DEFAULT_SIDEBAR_CONFIG: SidebarLayoutConfig = {
  variant: 'inset',
  collapsible: 'icon',
}

interface SidebarConfigContextValue {
  config: SidebarLayoutConfig
  updateConfig: (config: Partial<SidebarLayoutConfig>) => void
  resetConfig: () => void
}

const SidebarConfigContext = createContext<SidebarConfigContextValue | null>(null)

export function SidebarConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<SidebarLayoutConfig>(DEFAULT_SIDEBAR_CONFIG)

  const updateConfig = useCallback((next: Partial<SidebarLayoutConfig>) => {
    setConfig((prev) => ({ ...prev, ...next }))
  }, [])

  const resetConfig = useCallback(() => {
    setConfig(DEFAULT_SIDEBAR_CONFIG)
  }, [])

  return (
    <SidebarConfigContext.Provider value={{ config, updateConfig, resetConfig }}>
      {children}
    </SidebarConfigContext.Provider>
  )
}

export function useSidebarConfig() {
  const context = useContext(SidebarConfigContext)
  if (!context) {
    throw new Error('useSidebarConfig must be used within a SidebarConfigProvider')
  }
  return context
}
