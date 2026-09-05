'use client'

import { useState } from 'react'
import type { ThemeVars } from '@/lib/theme-presets'

function parseCssVars(css: string, selector: RegExp): ThemeVars {
  const match = css.match(selector)
  if (!match) return {}
  const vars: ThemeVars = {}
  for (const [, name, value] of match[1].matchAll(/--([^:]+):\s*([^;]+);/g)) {
    vars[name.trim()] = value.trim()
  }
  return vars
}

export function useImportThemeForm(onImport: (vars: ThemeVars) => void, onDone: () => void) {
  const [text, setText] = useState('')

  function submit() {
    const withoutComments = text.replace(/\/\*[\s\S]*?\*\//g, '')
    const light = parseCssVars(withoutComments, /:root\s*\{([^}]+)\}/)
    const dark = parseCssVars(withoutComments, /\.dark\s*\{([^}]+)\}/)
    onImport({ ...light, ...dark })
    setText('')
    onDone()
  }

  return { text, setText, submit }
}
