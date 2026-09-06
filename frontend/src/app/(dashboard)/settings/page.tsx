import { AccountFields } from '@/components/settings/account-fields'
import { Card, CardContent } from '@/components/ui/card'

export default function AccountSettingsPage() {
  return (
    <div className="lg:max-w-xl">
      <h3 className="text-lg font-medium">Account</h3>
      <p className="mb-4 text-sm text-muted-foreground">Your account details.</p>

      <Card>
        <CardContent className="space-y-6">
          <AccountFields />
        </CardContent>
      </Card>
    </div>
  )
}
