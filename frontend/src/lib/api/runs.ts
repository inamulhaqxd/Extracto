import { apiFetch, getAuthToken } from './client'
import type { ProcessingRun, DecisionStatus } from '@/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface UploadPdfResponse {
  document_id: string
  filename: string
  status: string
}

export interface UploadExcelResponse {
  workbook_id: string
  filename: string
  status: string
}

export interface CreateRunPayload {
  pdf_document_id: string
  workbook_id: string
  model_name?: string | null
}

export interface BackendDecision {
  requirement_id: string
  requirement_text: string
  section?: string | null
  status: string
  confidence: number
  reasoning?: string | null
  matched_value?: string | null
  resolving_layer?: string | null
  evidence?: Array<Record<string, unknown>>
  needs_review?: boolean
  review_notes?: string | null
}

export interface BackendRunResponse {
  run_id: string
  status: 'pending' | 'processing' | 'completed' | 'cancelled' | 'failed'
  progress: number
  current_step: string | null
  model_used?: string | null
  pdf_filename?: string | null
  workbook_filename?: string | null
  generated_file?: string | null
  total_requirements: number
  compliant_count: number
  non_compliant_count: number
  ambiguous_count: number
  not_found_count: number
  low_confidence_count: number
  decisions: BackendDecision[]
  started_at?: string | null
  completed_at?: string | null
  error_message?: string | null
}

interface ApiErrorResponse {
  detail?: string
}

export async function uploadPdf(file: File): Promise<UploadPdfResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const token = getAuthToken()
  const headers: Record<string, string> = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  const res = await fetch(`${API_BASE}/pdf/upload`, {
    method: 'POST',
    headers,
    body: formData,
    credentials: 'include',
  })

  if (!res.ok) {
    const error = (await res.json().catch(() => ({ detail: 'Failed to upload PDF' }))) as ApiErrorResponse
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  return (await res.json()) as UploadPdfResponse
}

export async function uploadExcel(file: File): Promise<UploadExcelResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const token = getAuthToken()
  const headers: Record<string, string> = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  const res = await fetch(`${API_BASE}/excel/upload`, {
    method: 'POST',
    headers,
    body: formData,
    credentials: 'include',
  })

  if (!res.ok) {
    const error = (await res.json().catch(() => ({ detail: 'Failed to upload Excel template' }))) as ApiErrorResponse
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  return (await res.json()) as UploadExcelResponse
}

export async function createRun(payload: CreateRunPayload): Promise<BackendRunResponse> {
  return apiFetch<BackendRunResponse>('/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getRun(runId: string): Promise<BackendRunResponse> {
  return apiFetch<BackendRunResponse>(`/runs/${runId}`)
}

export async function submitRunReview(
  runId: string,
  reviews: Array<{
    requirement_id: string
    status: string
    matched_value?: string | null
    confidence?: number | null
    review_notes?: string | null
  }>,
): Promise<BackendRunResponse> {
  return apiFetch<BackendRunResponse>(`/runs/${runId}/review`, {
    method: 'POST',
    body: JSON.stringify({ reviews }),
  })
}

export function getExcelDownloadUrl(filename: string, runId?: string): string {
  const token = getAuthToken()
  const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : ''
  if (runId) {
    return `${API_BASE}/runs/${encodeURIComponent(runId)}/download${tokenQuery}`
  }
  return `${API_BASE}/excel/download/${encodeURIComponent(filename)}${tokenQuery}`
}

export async function downloadExcelFile(filename: string, runId?: string): Promise<void> {
  const token = getAuthToken()
  const url = getExcelDownloadUrl(filename, runId)
  const res = await fetch(url, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: 'include',
  })

  if (!res.ok) {
    const error = (await res.json().catch(() => ({}))) as { detail?: string; message?: string }
    throw new Error(error.detail || error.message || `Download failed (HTTP ${res.status})`)
  }

  const blob = await res.blob()
  const blobUrl = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename.endsWith('.xlsx') ? filename : `${filename}.xlsx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(blobUrl)
}

export function transformBackendRun(backend: BackendRunResponse): ProcessingRun {
  return {
    id: backend.run_id,
    status: backend.status,
    progress: backend.progress,
    current_step: backend.current_step,
    pdf_filename: backend.pdf_filename || 'reference.pdf',
    excel_filename: backend.generated_file || backend.workbook_filename || 'output.xlsx',
    model: backend.model_used || 'Default',
    error_message: backend.error_message || undefined,
    created_at: backend.started_at || new Date().toISOString(),
    decisions: (backend.decisions || []).map((d) => {
      let mappedStatus: DecisionStatus = 'pending'
      const s = (d.status || '').toUpperCase()
      if (s.includes('COMPLIANT') && !s.includes('NON') && !s.includes('PARTIAL')) {
        mappedStatus = 'approved'
      } else if (s.includes('NON_COMPLIANT')) {
        mappedStatus = 'rejected'
      }

      return {
        id: d.requirement_id,
        requirement: d.requirement_text,
        extracted_value: d.matched_value || '',
        confidence: d.confidence,
        status: mappedStatus,
        override_value: undefined,
      }
    }),
  }
}
