'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getMe } from '@/lib/api/auth'

export function useRootRedirect() {
  const router = useRouter()

  useEffect(() => {
    getMe()
      .then(() => router.replace('/dashboard'))
      .catch(() => router.replace('/sign-in'))
  }, [router])
}
