'use client'

import { useAuthGuard } from '@/hooks/use-auth-guard'
import { Spinner } from '@/components/ui/spinner'

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const checked = useAuthGuard()

  if (!checked) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="size-8" />
      </div>
    )
  }

  return <>{children}</>
}
