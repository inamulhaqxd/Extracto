'use client'

import { useEffect, useState } from 'react'
import { getModelPreference, setModelPreference } from '@/lib/api/ai'

const LOCAL_MODEL_KEY = 'tender_preferred_model'

export function useModelPreference() {
  const [modelTag, setModelTagState] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null
    try {
      return localStorage.getItem(LOCAL_MODEL_KEY)
    } catch {
      return null
    }
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let mounted = true

    getModelPreference()
      .then((pref) => {
        if (mounted && pref.model_tag) {
          setModelTagState(pref.model_tag)
          try {
            localStorage.setItem(LOCAL_MODEL_KEY, pref.model_tag)
          } catch {
            // Ignore localStorage errors
          }
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (mounted) setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [])

  async function setModelTag(tag: string) {
    setSaving(true)
    setModelTagState(tag)
    try {
      localStorage.setItem(LOCAL_MODEL_KEY, tag)
    } catch {
      // Ignore localStorage errors
    }

    try {
      const pref = await setModelPreference(tag)
      setModelTagState(pref.model_tag)
    } catch (err: unknown) {
      console.warn('Failed to sync model preference to backend:', err)
    } finally {
      setSaving(false)
    }
  }

  return { modelTag, setModelTag, loading, saving }
}
