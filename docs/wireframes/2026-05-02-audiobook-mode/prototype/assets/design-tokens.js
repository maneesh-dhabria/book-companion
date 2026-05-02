// Generated from frontend/DESIGN.md (2026-05-02). Read at runtime by atoms.
window.__designTokens = {
  color: {
    bg: { primary: "#ffffff", secondary: "#f8f9fa", tertiary: "#f1f3f5", elevated: "#ffffff" },
    text: { primary: "#1a1a2e", secondary: "#6b7280", muted: "#9ca3af", accent: "#4f46e5" },
    border: { default: "#e5e7eb", strong: "#d1d5db" },
    accent: { base: "#4f46e5", hover: "#4338ca" },
    status: { success: "#16a34a", warning: "#d97706", error: "#dc2626" },
    sidebar: { bg: "#1e1e2e", text: "#cdd6f4", active: "#4f46e5" },
    highlight: { saved: "#fef9c3" }
  },
  font: {
    sans: '"Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif',
    mono: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace'
  },
  size: { xs: "11px", sm: "13px", base: "14px", md: "16px", lg: "20px", xl: "28px" },
  radius: { default: "8px", large: "14px", pill: "999px" },
  shadow: {
    default: "0 1px 2px rgba(0,0,0,.04), 0 4px 12px rgba(0,0,0,.04)",
    raised: "0 -2px 12px rgba(0,0,0,.06)",
    modal: "0 20px 50px rgba(0,0,0,.18)"
  },
  spacing: { 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32 },
  interaction: {
    modals: { style: "centered", dismiss: ["backdrop-click", "esc-key", "explicit-button"] },
    destructiveActions: { confirmation: "type-to-confirm" },
    focus: { trapInModals: true, visibleStyle: "outline: 2px solid #4f46e5; outline-offset: 2px;" },
    defaultStates: { empty: "minimal", loading: "skeleton", error: "inline-banner" },
    shortcuts: {
      "Space": "play/pause active audio",
      "ArrowLeft": "previous sentence",
      "ArrowRight": "next sentence",
      "?": "open keyboard shortcut help",
      "/": "focus search",
      "Esc": "close modal / dismiss banner"
    },
    audio: { autoAdvance: true, rememberPosition: true }
  },
  content: {
    voice: { tone: "calm, factual, second-person" },
    buttonVerbs: { primary: "Save", create: "Create", destroy: "Delete", listen: "Listen", generate: "Generate", regenerate: "Regenerate" },
    formats: { date: "MMM D, YYYY", duration: "M:SS / M:SS", fileSize: "iec-binary", sentenceIndex: "sentence N of M" }
  }
};
