import type { ProcessingRun, RequirementDecision } from '@/types'

const REQUIREMENTS: Omit<RequirementDecision, 'status' | 'override_value'>[] = [
  {
    id: 'req-1',
    requirement: 'Maximum operating temperature range',
    extracted_value: '-20°C to 60°C',
    confidence: 0.94,
  },
  {
    id: 'req-2',
    requirement: 'Power supply voltage tolerance',
    extracted_value: '220V ± 10%',
    confidence: 0.88,
  },
  {
    id: 'req-3',
    requirement: 'Ingress protection rating',
    extracted_value: 'IP65',
    confidence: 0.97,
  },
  {
    id: 'req-4',
    requirement: 'Warranty period',
    extracted_value: '24 months',
    confidence: 0.62,
  },
  {
    id: 'req-5',
    requirement: 'Certification standard',
    extracted_value: 'ISO 9001, CE',
    confidence: 0.79,
  },
]

export function buildMockRun(overrides: Partial<ProcessingRun> = {}): ProcessingRun {
  return {
    id: 'run-mock-001',
    status: 'pending',
    progress: 0,
    current_step: null,
    pdf_filename: 'reference-spec.pdf',
    excel_filename: 'compliance-template.xlsx',
    model: 'qwen2.5:3b',
    decisions: REQUIREMENTS.map((r) => ({ ...r, status: 'pending' as const })),
    created_at: new Date().toISOString(),
    ...overrides,
  }
}
