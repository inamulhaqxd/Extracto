'use client'

import { useEffect, useState } from 'react'
import { listModels } from '@/lib/api/ai'
import type { ModelsListResponse } from '@/types'

export function useModels() {
  const [data, setData] = useState<ModelsListResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true

    listModels()
      .then((result) => {
        if (mounted) setData(result)
      })
      .catch(() => undefined)
      .finally(() => {
        if (mounted) setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [])

  return { models: data?.models ?? [], defaultModel: data?.default_model ?? null, loading }
}
