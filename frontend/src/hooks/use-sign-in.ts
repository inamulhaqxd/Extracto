import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { login } from '@/lib/api/auth'
import { setAuthToken } from '@/lib/api/client'

const signInSchema = z.object({
  email: z.string().min(1, 'Email or username is required'),
  password: z.string().min(1, 'Password is required'),
})

type SignInValues = z.infer<typeof signInSchema>

const FRIENDLY_ERRORS: Record<string, string> = {
  'Invalid credentials': 'Email or password is incorrect.',
  'Invalid email or password': 'Email or password is incorrect.',
  'Account is deactivated': 'Your account has been deactivated.',
  'User not found': 'No account found with these credentials.',
  'Too many requests': 'Too many attempts. Please try again later.',
  'Failed to fetch': 'Unable to connect to the backend server. Please verify the API is running.',
}

function friendlyError(raw: string): string {
  if (FRIENDLY_ERRORS[raw]) {
    return FRIENDLY_ERRORS[raw]
  }
  return raw.trim() ? raw : 'Something went wrong. Please try again.'
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
        const res = await login({
          email: values.email,
          username: values.email,
          password: values.password,
        })
        setAuthToken(res.access_token)
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
