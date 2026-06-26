// Globals provided by the bundled site scripts (shared.js, i18n-data.js).
export interface BenroShared {
  applyLang?: (lang: string) => unknown
  initReveal?: () => void
  initCounters?: () => void
  initYear?: () => void
}

declare global {
  interface Window {
    BenroShared?: BenroShared
    I18N?: Record<string, Record<string, string>>
    applyLang?: (lang: string) => void
  }
}
