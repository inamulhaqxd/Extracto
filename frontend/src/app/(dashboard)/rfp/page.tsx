import { RunFlow } from '@/components/runs/run-flow'

export default function RfpPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Workspace</h1>
        <p className="text-muted-foreground">
          Upload your specification PDF and we&apos;ll extract the requirements, let you double-check them,
          and hand you back a filled-in Excel sheet.
        </p>
      </div>

      <RunFlow />
    </div>
  )
}
