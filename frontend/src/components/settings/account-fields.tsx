'use client'

import { useCurrentUser } from '@/hooks/use-current-user'
import { Skeleton } from '@/components/ui/skeleton'

export function AccountFields() {
  const user = useCurrentUser()

  if (!user) {
    return (
      <>
        <Skeleton className="h-9 w-56" />
        <Skeleton className="h-9 w-56" />
        <Skeleton className="h-9 w-32" />
      </>
    )
  }

  return (
    <>
      <div>
        <div className="text-sm font-medium">Username</div>
        <div className="mt-1 text-sm text-muted-foreground">{user.username}</div>
      </div>

      <div>
        <div className="text-sm font-medium">Email</div>
        <div className="mt-1 text-sm text-muted-foreground">{user.email}</div>
      </div>

      <div>
        <div className="text-sm font-medium">Role</div>
        <div className="mt-1 text-sm text-muted-foreground">
          {user.is_admin ? 'Admin' : 'Member'}
        </div>
      </div>
    </>
  )
}
