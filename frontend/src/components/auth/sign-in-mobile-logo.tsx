import { FileText } from 'lucide-react'

export function SignInMobileLogo() {
  return (
    <div className="flex items-center justify-center gap-3 lg:hidden">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
        <FileText className="size-5" />
      </div>
      <span className="text-lg font-semibold">Extracto AI</span>
    </div>
  )
}
