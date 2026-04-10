# V2 Web Interface Wireframes

Interactive HTML wireframes for the Book Companion web interface, created during brainstorming sessions on 2026-04-10. Open any `.html` file in a browser to view (all files are self-contained with embedded CSS, support light/dark mode).

## Final Designs

Each component folder contains both desktop (`*-final.html`) and mobile (`*-mobile.html`) wireframes.

### App Shell
| File | Description |
|------|-------------|
| `app_shell/app-shell-final.html` | Desktop — icon rail sidebar, persistent search bar, upload button, content placeholder |
| `app_shell/app-shell-mobile.html` | Mobile — bottom tab bar, adaptive header (hamburger vs back arrow), search tab |

### Library
| File | Description |
|------|-------------|
| `library/library-final.html` | Desktop — custom views, multi-select filter dropdowns, grid/list/table, book cards |
| `library/library-mobile.html` | Mobile — list view, scrollable view tabs, compact filters, book rows |

### Book Detail / Reader
| File | Description |
|------|-------------|
| `book_detail/book-detail-final.html` | Desktop — breadcrumb nav, chapter dropdown TOC, original/summary toggle, context sidebar |
| `book_detail/book-detail-mobile.html` | Mobile — single column reader, bottom action bar, annotation bottom sheet |

### Reader Settings
| File | Description |
|------|-------------|
| `reader_settings/reader-settings-final.html` | Desktop — popover with visual presets, font buttons, named steppers, color picker, live preview |
| `reader_settings/reader-settings-mobile.html` | Mobile — full-screen modal, 2x2 preset grid, wrapping controls, swatches, preview |

### AI Chat
| File | Description |
|------|-------------|
| `ai_chat/ai-chat-final.html` | Desktop — sidebar tab with thread list, active thread, text selection context, save-as-note |
| `ai_chat/ai-chat-mobile.html` | Mobile — bottom sheet with thread list + active thread states, chat input |

### Upload & Processing
| File | Description |
|------|-------------|
| `upload_processing/upload-step1-final.html` | Desktop — Step 1 drag-drop zone + file-selected parsing state |
| `upload_processing/upload-flow-final.html` | Desktop — Steps 2-5: metadata, structure review, preset selection, progress tracking |
| `upload_processing/upload-edge-cases.html` | Desktop — duplicate detection, format conflicts, preset management in Settings |
| `upload_processing/upload-mobile.html` | Mobile — full-width wizard steps, touch-adapted file picker, stacked forms |

### Search
| File | Description |
|------|-------------|
| `search/search-final.html` | Desktop — ⌘K command palette + full results page with sidebar filters |
| `search/search-mobile.html` | Mobile — full-screen search, filter chips replacing sidebar, grouped results |

### Annotations
| File | Description |
|------|-------------|
| `annotations/annotations-final.html` | Desktop — global browser, filter by book/type/tags, grouped cards with links |
| `annotations/annotations-mobile.html` | Mobile — single column, filter chips, collapsible book groups |

### Concepts Explorer
| File | Description |
|------|-------------|
| `concepts_explorer/concepts-explorer-final.html` | Desktop — two-panel list + detail, cross-book concepts, editable definitions |
| `concepts_explorer/concepts-mobile.html` | Mobile — single column list → tap to push detail view |

### Editing Interfaces
| File | Description |
|------|-------------|
| `editing/editing-final.html` | All editing wireframes: summary (inline), annotation (card), concept (inline), metadata (modal), sections (merge/split/reorder) |

### Image Handling
| File | Description |
|------|-------------|
| `images/image-handling-final.html` | Images in original content (relevance badges), summary references (inline/collapsed), lightbox, AI context |

### Multi-Device / Mobile
| File | Description |
|------|-------------|
| `multi_device/multi-device-final.html` | LAN access architecture, QR code, responsive breakpoints, mobile adaptation patterns |
| `multi_device/mobile-views-final.html` | Consolidated view of ALL mobile wireframes on one page (overview reference) |

## Iterations

Earlier explorations and alternative approaches, preserved in `iterations/` subfolders.

### `app_shell/iterations/`
| File | Description |
|------|-------------|
| `app-shell-v1.html` | Initial app shell with library content mixed in |
| `architecture-approach.html` | Architecture decision — reader-centric vs dashboard vs command-palette |

### `library/iterations/`
| File | Description |
|------|-------------|
| `library-filters-v1.html` | Two-tier filtering — status tabs + composable filter chips |
| `library-filters-v2.html` | Tags as pills + inline author dropdown |
| `library-views.html` | Introduction of Notion-style saved views |

### `book_detail/iterations/`
| File | Description |
|------|-------------|
| `book-detail-v1.html` | Initial two-panel with persistent left TOC |
| `book-detail-approaches.html` | 4 approaches — three-panel, slide-out, inline blocks, reader + context |

### `upload_processing/iterations/`
| File | Description |
|------|-------------|
| `upload-processing-v1.html` | Initial 3-step wizard before expansion to 5 steps |
