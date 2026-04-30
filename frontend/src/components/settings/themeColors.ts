export interface ThemeColors {
  bg: string
  fg: string
  accent: string
}

export const themeMap: Record<string, ThemeColors> = {
  light: { bg: '#ffffff', fg: '#1f2937', accent: '#2563eb' },
  sepia: { bg: '#f4ecd8', fg: '#3a2f1d', accent: '#8b5a2b' },
  dark: { bg: '#1f2937', fg: '#e5e7eb', accent: '#60a5fa' },
  night: { bg: '#0f172a', fg: '#cbd5e1', accent: '#3b82f6' },
  paper: { bg: '#fafaf5', fg: '#3a3a3a', accent: '#5b21b6' },
  contrast: { bg: '#000000', fg: '#ffffff', accent: '#fbbf24' },
}
