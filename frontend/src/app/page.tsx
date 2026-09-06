'use client'

import { useRootRedirect } from '@/hooks/use-root-redirect'

export default function Home() {
  useRootRedirect()

  return null
}
