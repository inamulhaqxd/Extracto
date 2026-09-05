'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getMe } from '@/lib/api/auth'

export function useAuthGuard() {
  const router = useRouter()
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    let mounted = true

    getMe()
      .then(() => {
        if (mounted) queueMicrotask(() => setChecked(true))
      })
      .catch(() => router.replace('/sign-in'))

    return () => {
      mounted = false
    }
  }, [router])

  return checked
}
