import { Controller } from 'react-hook-form'
import { CircleAlert, Eye, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Spinner } from '@/components/ui/spinner'
import { Field, FieldLabel, FieldError } from '@/components/ui/field'
import { InputGroup, InputGroupInput, InputGroupButton } from '@/components/ui/input-group'
import type { UseFormReturn } from 'react-hook-form'

interface SignInFormProps {
  form: UseFormReturn<{ email: string; password: string }>
  error: string | null
  loading: boolean
  showPassword: boolean
  onTogglePassword: () => void
  onSubmit: (e: React.SubmitEvent<HTMLFormElement>) => void
}

export function SignInForm({
  form,
  error,
  loading,
  showPassword,
  onTogglePassword,
  onSubmit,
}: SignInFormProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <Controller
        name="email"
        control={form.control}
        render={({ field, fieldState }) => (
          <Field data-invalid={fieldState.invalid}>
            <FieldLabel htmlFor={field.name}>Email or Username</FieldLabel>
            <InputGroup className="h-12 bg-muted/30 border-muted-foreground/20 transition-colors focus-within:bg-background">
              <InputGroupInput
                {...field}
                id={field.name}
                type="text"
                placeholder="admin or you@example.com"
                disabled={loading}
                aria-invalid={fieldState.invalid}
              />
            </InputGroup>
            {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
          </Field>
        )}
      />

      <Controller
        name="password"
        control={form.control}
        render={({ field, fieldState }) => (
          <Field data-invalid={fieldState.invalid}>
            <FieldLabel htmlFor={field.name}>Password</FieldLabel>
            <InputGroup className="h-12 bg-muted/30 border-muted-foreground/20 transition-colors focus-within:bg-background">
              <InputGroupInput
                {...field}
                id={field.name}
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                disabled={loading}
                aria-invalid={fieldState.invalid}
              />
              <InputGroupButton
                onClick={onTogglePassword}
                variant="ghost"
                size="sm"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? (
                  <EyeOff className="size-5" />
                ) : (
                  <Eye className="size-5" />
                )}
              </InputGroupButton>
            </InputGroup>
            {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
          </Field>
        )}
      />

      {error && (
        <Alert variant="destructive">
          <CircleAlert />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Button
        className="h-12 w-full font-medium"
        type="submit"
        isDisabled={loading}
      >
        {loading ? (
          <span className="flex items-center gap-2">
            <Spinner />
            Signing in...
          </span>
        ) : (
          'Sign in'
        )}
      </Button>
    </form>
  )
}
