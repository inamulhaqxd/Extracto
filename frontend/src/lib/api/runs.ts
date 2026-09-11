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

export interface BackendSlotAssignment {
  slot_type?: string
  cell_coordinate?: string
  value?: string
  needs_review?: boolean
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
  slot_assignments?: Record<string, BackendSlotAssignment>
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

export async function listRuns(): Promise<BackendRunResponse[]> {
  return apiFetch<BackendRunResponse[]>('/runs')
}

export async function submitRunReview(
  runId: string,
  reviews: Array<{
    requirement_id: string
    status: string
    matched_value?: string | null
    confidence?: number | null
    review_notes?: string | null
    slot_overrides?: Record<string, string> | null
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
      if (s.includes('OVERRIDDEN')) {
        mappedStatus = 'overridden'
      } else if (s.includes('COMPLIANT') && !s.includes('NON') && !s.includes('PARTIAL')) {
        mappedStatus = 'approved'
      } else if (s.includes('NON_COMPLIANT')) {
        mappedStatus = 'rejected'
      }

      const slotsList = d.slot_assignments
        ? Object.entries(d.slot_assignments).map(([key, slot]) => ({
            key,
            slot_type: slot.slot_type || key,
            cell_coordinate: slot.cell_coordinate || '',
            value: slot.value != null ? String(slot.value) : '',
            needs_review: Boolean(slot.needs_review),
          }))
        : []

      return {
        id: d.requirement_id,
        requirement: d.requirement_text,
        extracted_value: d.matched_value || '',
        confidence: d.confidence,
        status: mappedStatus,
        override_value: s.includes('OVERRIDDEN') ? (d.matched_value || undefined) : undefined,
        slots: slotsList,
      }
    }),
  }
}

export interface FingerprintGroup {
  fingerprint: string
  label: string
  sample_count: number
  accuracy: number
}

export interface QualityMetricsResponse {
  total_runs: number
  reviewed_runs: number
  total_reviewed_examples: number
  exact_correction_accuracy: number
  low_confidence_failures: number
  active_dataset_version: string
  layer_breakdown: {
    deterministic_rules: number
    verified_llm: number
    fallback: number
  }
  fingerprint_groups: FingerprintGroup[]
}

export interface CreateSnapshotResponse {
  snapshot_id: string
  file_path: string
  item_count: number
  created_at: string
}

export interface RunInspectionItem {
  requirement_id: string
  requirement_text: string
  predicted_status: string
  predicted_value: string
  confidence: number
  reasoning: string
  citation: string
  corrected_status: string
  corrected_value: string
  review_notes?: string | null
  is_exact_match: boolean
}

export async function getQualityMetrics(): Promise<QualityMetricsResponse> {
  return apiFetch<QualityMetricsResponse>('/runs/quality/metrics')
}

export async function createDatasetSnapshot(): Promise<CreateSnapshotResponse> {
  return apiFetch<CreateSnapshotResponse>('/runs/quality/snapshots', {
    method: 'POST',
  })
}

export async function getRunInspections(runId: string): Promise<RunInspectionItem[]> {
  return apiFetch<RunInspectionItem[]>(`/runs/${runId}/inspections`)
}

