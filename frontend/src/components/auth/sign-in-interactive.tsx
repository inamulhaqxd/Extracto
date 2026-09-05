'use client'

import { useSignIn } from '@/hooks/use-sign-in'
import { SignInForm } from '@/components/auth/sign-in-form'

export function SignInInteractive() {
  const {
    form,
    handleSubmit,
    onSubmit,
    error,
    loading,
    showPassword,
    setShowPassword,
  } = useSignIn()

  return (
    <SignInForm
      form={form}
      error={error}
      loading={loading}
      showPassword={showPassword}
      onTogglePassword={() => setShowPassword(!showPassword)}
      onSubmit={handleSubmit(onSubmit)}
    />
  )
}
