'use client'

import { useState } from 'react'

export function useRequirementOverride(initialValue: string) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(initialValue)

  function openDialog() {
    setDraft(initialValue)
    setOpen(true)
  }

  function closeDialog() {
    setOpen(false)
  }

  return { open, setOpen, draft, setDraft, openDialog, closeDialog }
}
