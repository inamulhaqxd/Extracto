'use client'

import { useState } from 'react'

export function useImportDialog() {
  const [importOpen, setImportOpen] = useState(false)
  return { importOpen, setImportOpen }
}
