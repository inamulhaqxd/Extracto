export type ThemeVars = Record<string, string>

export interface ThemePreset {
  id: string
  name: string
  swatch: [string, string, string, string]
  light: ThemeVars
  dark: ThemeVars
}

function accentPreset(
  id: string,
  name: string,
  hue: number,
  chroma: number,
  swatch: [string, string, string, string]
): ThemePreset {
  const primaryLight = `oklch(0.5 ${chroma} ${hue})`
  const primaryDark = `oklch(0.65 ${chroma * 0.9} ${hue})`
  const accentLight = `oklch(0.94 ${chroma * 0.15} ${hue})`
  const accentDark = `oklch(0.3 ${chroma * 0.4} ${hue})`

  return {
    id,
    name,
    swatch,
    light: {
      primary: primaryLight,
      'primary-foreground': 'oklch(0.985 0 0)',
      accent: accentLight,
      'accent-foreground': primaryLight,
      ring: primaryLight,
      'sidebar-primary': primaryLight,
      'sidebar-primary-foreground': 'oklch(0.985 0 0)',
      'sidebar-accent': accentLight,
      'sidebar-accent-foreground': primaryLight,
      'sidebar-ring': primaryLight,
    },
    dark: {
      primary: primaryDark,
      'primary-foreground': 'oklch(0.145 0 0)',
      accent: accentDark,
      'accent-foreground': `oklch(0.85 ${chroma * 0.5} ${hue})`,
      ring: primaryDark,
      'sidebar-primary': primaryDark,
      'sidebar-primary-foreground': 'oklch(0.145 0 0)',
      'sidebar-accent': accentDark,
      'sidebar-accent-foreground': `oklch(0.85 ${chroma * 0.5} ${hue})`,
      'sidebar-ring': primaryDark,
    },
  }
}

const DEFAULT_PRESET: ThemePreset = {
  id: 'default',
  name: 'Default',
  swatch: ['#171717', '#f5f5f5', '#f5f5f5', '#a3a3a3'],
  light: {
    primary: 'oklch(0.205 0 0)',
    'primary-foreground': 'oklch(0.985 0 0)',
    accent: 'oklch(0.97 0 0)',
    'accent-foreground': 'oklch(0.205 0 0)',
    ring: 'oklch(0.708 0 0)',
    'sidebar-primary': 'oklch(0.205 0 0)',
    'sidebar-primary-foreground': 'oklch(0.985 0 0)',
    'sidebar-accent': 'oklch(0.97 0 0)',
    'sidebar-accent-foreground': 'oklch(0.205 0 0)',
    'sidebar-ring': 'oklch(0.708 0 0)',
  },
  dark: {
    primary: 'oklch(0.922 0 0)',
    'primary-foreground': 'oklch(0.205 0 0)',
    accent: 'oklch(0.269 0 0)',
    'accent-foreground': 'oklch(0.985 0 0)',
    ring: 'oklch(0.556 0 0)',
    'sidebar-primary': 'oklch(0.65 0.2 264.376)',
    'sidebar-primary-foreground': 'oklch(0.145 0 0)',
    'sidebar-accent': 'oklch(0.269 0 0)',
    'sidebar-accent-foreground': 'oklch(0.985 0 0)',
    'sidebar-ring': 'oklch(0.556 0 0)',
  },
}

export const THEME_PRESETS: ThemePreset[] = [
  DEFAULT_PRESET,
  accentPreset('blue', 'Blue', 258, 0.19, ['#3b5bdb', '#e7ebfd', '#e7ebfd', '#8ba0f7']),
  accentPreset('violet', 'Violet', 293, 0.19, ['#7c3aed', '#f0e8fd', '#f0e8fd', '#bd9af5']),
  accentPreset('emerald', 'Emerald', 155, 0.16, ['#0f9d64', '#dcf5e9', '#dcf5e9', '#7fd8ac']),
  accentPreset('rose', 'Rose', 15, 0.2, ['#e11d48', '#fce4e8', '#fce4e8', '#f28ba0']),
  accentPreset('orange', 'Orange', 55, 0.18, ['#ea580c', '#fde8d8', '#fde8d8', '#f5a768']),
  accentPreset('teal', 'Teal', 190, 0.14, ['#0d9488', '#daf3f1', '#daf3f1', '#7ecdc6']),
  accentPreset('pink', 'Pink', 350, 0.19, ['#db2777', '#fbe3ee', '#fbe3ee', '#ee8fbd']),
]

export const RADIUS_PRESETS = [
  { name: '0', value: '0px' },
  { name: '4', value: '4px' },
  { name: '8', value: '8px' },
  { name: '10', value: '10px' },
  { name: '12', value: '12px' },
  { name: '16', value: '16px' },
] as const
