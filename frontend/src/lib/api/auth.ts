import type { LoginRequest, TokenResponse, User } from '@/types'
import { apiFetch, removeAuthToken } from './client'

export function login(data: LoginRequest): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function getMe(): Promise<User> {
  return apiFetch<User>('/auth/me')
}

export function logout(): Promise<unknown> {
  removeAuthToken()
  return apiFetch('/auth/logout', { method: 'POST' }).catch(() => ({}))
}
