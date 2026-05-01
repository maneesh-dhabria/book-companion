// Bundle reader webfonts via @fontsource so reader presets render with their
// intended typography on any host machine. Selective weights per FR-40.
//
// We use latin-only subsets (`<weight>.css` ships *all* unicode subsets;
// `latin-<weight>.css` ships latin-only) to stay under the NFR-05 600 KB
// woff2 budget. Reader content is English-only today; if i18n requirements
// change, swap to the full `<weight>.css` import.
//
// All @fontsource packages default to `font-display: swap` (verified in
// node_modules/@fontsource/inter/latin-400.css).

// Inter: 400 + 700
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-700.css'
// Merriweather: 400 + 700
import '@fontsource/merriweather/latin-400.css'
import '@fontsource/merriweather/latin-700.css'
// Lora: 400 + 600
import '@fontsource/lora/latin-400.css'
import '@fontsource/lora/latin-600.css'
// Fira Code: 400
import '@fontsource/fira-code/latin-400.css'
// Source Serif Pro: 400 + 700
import '@fontsource/source-serif-pro/latin-400.css'
import '@fontsource/source-serif-pro/latin-700.css'
