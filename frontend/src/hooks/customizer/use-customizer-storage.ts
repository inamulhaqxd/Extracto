'use client'

import type { SidebarLayoutConfig } from '@/contexts/sidebar-config-context'

export interface CustomizerStorageState {
  presetId: string | null
  radius: string | null
  brandColors: Record<string, string>
  sidebar: SidebarLayoutConfig | null
}

const STORAGE_KEY = 'tenderflow.customizer'

export function loadCustomizerState(): CustomizerStorageState | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as CustomizerStorageState) : null
  } catch {
    return null
  }
}

export function saveCustomizerState(state: Partial<CustomizerStorageState>) {
  if (typeof window === 'undefined') return
  const current = loadCustomizerState() ?? {
    presetId: null,
    radius: null,
    brandColors: {},
    sidebar: null,
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, ...state }))
}

export function clearCustomizerState() {
  if (typeof window === 'undefined') return
  localStorage.removeItem(STORAGE_KEY)
}
