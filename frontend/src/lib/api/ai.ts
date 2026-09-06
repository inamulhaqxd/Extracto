import type { ModelPreference, ModelsListResponse } from '@/types'
import { apiFetch } from './client'

export function listModels(): Promise<ModelsListResponse> {
  return apiFetch<ModelsListResponse>('/ai/models')
}

export function getModelPreference(): Promise<ModelPreference> {
  return apiFetch<ModelPreference>('/ai/preference')
}

export function setModelPreference(modelTag: string): Promise<ModelPreference> {
  return apiFetch<ModelPreference>('/ai/preference', {
    method: 'PUT',
    body: JSON.stringify({ model_tag: modelTag }),
  })
}
