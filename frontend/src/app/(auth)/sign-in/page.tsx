import { SignInBrandPanel } from '@/components/auth/sign-in-brand-panel'
import { SignInInteractive } from '@/components/auth/sign-in-interactive'
import { SignInMobileLogo } from '@/components/auth/sign-in-mobile-logo'
import { ThemeToggler } from '@/components/theme-toggler'

export default function SignInPage() {
  return (
    <div className="relative grid min-h-screen w-full lg:grid-cols-2">
      <div className="absolute top-4 right-4 z-50">
        <ThemeToggler />
      </div>

      <SignInBrandPanel />

      <div className="flex items-center justify-center bg-background p-6 lg:p-12">
        <div className="mx-auto w-full max-w-100 space-y-8">
          <SignInMobileLogo />

          <div className="space-y-2 text-center lg:text-left">
            <h1 className="text-3xl font-bold tracking-tight">Welcome back</h1>
            <p className="text-muted-foreground">
              Sign in to your account to continue
            </p>
          </div>

          <SignInInteractive />
        </div>
      </div>
    </div>
  )
}
