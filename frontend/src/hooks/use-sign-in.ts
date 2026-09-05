import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { login } from '@/lib/api/auth'

const signInSchema = z.object({
  email: z.email('Please enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})

type SignInValues = z.infer<typeof signInSchema>

const FRIENDLY_ERRORS: Record<string, string> = {
  'Invalid credentials': 'Email or password is incorrect.',
  'Too many requests': 'Too many attempts. Please try again later.',
}

function friendlyError(raw: string): string {
  return FRIENDLY_ERRORS[raw] || 'Something went wrong. Please try again.'
}

export function useSignIn() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()
  const [showPassword, setShowPassword] = useState(false)

  const form = useForm<SignInValues>({
    resolver: zodResolver(signInSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })

  async function onSubmit(values: SignInValues) {
    setError(null)
    startTransition(async () => {
      try {
        await login({ email: values.email, password: values.password })
        router.push('/dashboard')
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Login failed'
        setError(friendlyError(message))
      }
    })
  }

  return {
    form,
    handleSubmit: form.handleSubmit,
    onSubmit,
    error,
    loading: isPending,
    showPassword,
    setShowPassword,
  }
}
