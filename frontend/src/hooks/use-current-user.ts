'use client'

import { useEffect, useState } from 'react'
import { getMe } from '@/lib/api/auth'
import type { User } from '@/types'

export function useCurrentUser() {
  const [user, setUser] = useState<User | null>(null)

  useEffect(() => {
    let mounted = true

    getMe()
      .then((data) => {
        if (mounted) setUser(data)
      })
      .catch(() => undefined)

    return () => {
      mounted = false
    }
  }, [])

  return user
}
