'use client'

import { useState } from 'react'

export function useUploadForm() {
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [excelFile, setExcelFile] = useState<File | null>(null)

  const canStart = pdfFile !== null && excelFile !== null

  return { pdfFile, setPdfFile, excelFile, setExcelFile, canStart }
}
