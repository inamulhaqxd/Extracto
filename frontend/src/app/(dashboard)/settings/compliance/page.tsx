import { ModelPicker } from '@/components/settings/model-picker'
import { Card, CardContent } from '@/components/ui/card'

export default function ComplianceSettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Compliance</h2>
        <p className="text-sm text-muted-foreground">
          Choose the default AI model for new compliance runs.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-2">
          <ModelPicker />
        </CardContent>
      </Card>
    </div>
  )
}
