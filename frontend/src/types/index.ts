export interface User {
  id: string
  username: string
  email: string
  is_admin: boolean
}

export interface TokenResponse {
  access_token: string
  token_type?: string
  user: User
}

export interface LoginRequest {
  email?: string
  username?: string
  password: string
}

export interface RfpDocument {
  id: string
  title: string
  filename: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  uploaded_at: string
  completed_at?: string
}

export type RunStatus = 'pending' | 'processing' | 'completed' | 'cancelled' | 'failed'

export type DecisionStatus = 'pending' | 'approved' | 'rejected' | 'overridden'

export interface RequirementDecision {
  id: string
  requirement: string
  extracted_value: string
  confidence: number
  status: DecisionStatus
  override_value?: string
}

export interface ProcessingRun {
  id: string
  status: RunStatus
  progress: number
  current_step: string | null
  pdf_filename: string
  excel_filename: string
  model: string
  error_message?: string
  decisions: RequirementDecision[]
  created_at: string
}

export interface ModelInfo {
  id: string
  name: string
  tag: string
  label: string
  ram_usage: string
  context_length: string
  is_default: boolean
  is_available: boolean
}

export interface ModelsListResponse {
  models: ModelInfo[]
  default_model: string
  ollama_reachable: boolean
  warning: string | null
}

export interface ModelPreference {
  model_tag: string
  model_name: string | null
}
