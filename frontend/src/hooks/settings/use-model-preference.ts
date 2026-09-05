'use client'

import { useEffect, useState } from 'react'
import { getModelPreference, setModelPreference } from '@/lib/api/ai'

export function useModelPreference() {
  const [modelTag, setModelTagState] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let mounted = true

    getModelPreference()
      .then((pref) => {
        if (mounted) setModelTagState(pref.model_tag)
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
    try {
      const pref = await setModelPreference(tag)
      setModelTagState(pref.model_tag)
    } finally {
      setSaving(false)
    }
  }

  return { modelTag, setModelTag, loading, saving }
}
