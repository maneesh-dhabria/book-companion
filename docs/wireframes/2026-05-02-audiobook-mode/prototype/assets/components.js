/* Book Companion audiobook prototype — shared atoms.
 * JSX compiled at runtime by Babel-standalone. Token values come from
 * window.__designTokens; structural styles come from prototype.css +
 * design-overlay.css.
 */

const Button = ({ variant = "primary", onClick, children, disabled, loading, type = "button", ariaLabel, size = "md", className = "" }) => (
  <button
    type={type}
    className={`btn btn--${variant} btn--${size} ${loading ? "btn--loading" : ""} ${className}`}
    onClick={onClick}
    disabled={disabled || loading}
    aria-label={ariaLabel}
  >
    {loading ? <Spinner size="sm" /> : children}
  </button>
);

const IconButton = ({ icon, onClick, ariaLabel, variant = "ghost", disabled, className = "" }) => (
  <button
    type="button"
    className={`btn btn--${variant} btn--icon ${className}`}
    onClick={onClick}
    aria-label={ariaLabel}
    disabled={disabled}
  >
    <span aria-hidden="true">{icon}</span>
  </button>
);

const Input = ({ label, value, onChange, error, type = "text", placeholder, required, name, autoComplete, hint }) => (
  <label className={`field ${error ? "field--error" : ""}`}>
    {label && <span className="field__label">{label}{required && <span className="field__required" aria-label="required"> *</span>}</span>}
    <input
      className="field__input"
      type={type}
      name={name}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      autoComplete={autoComplete}
      aria-invalid={!!error}
      aria-describedby={error ? `${name}-error` : hint ? `${name}-hint` : undefined}
    />
    {hint && !error && <span id={`${name}-hint`} className="field__hint">{hint}</span>}
    {error && <span id={`${name}-error`} className="field__error" role="alert">{error}</span>}
  </label>
);

const Modal = ({ open, onClose, title, children, footer, size = "md" }) => {
  const dialogRef = React.useRef(null);
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    // Focus trap (simple): focus first focusable inside dialog
    setTimeout(() => {
      const f = dialogRef.current?.querySelector("button, input, select, textarea, [tabindex]:not([tabindex='-1'])");
      f?.focus();
    }, 0);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className={`modal modal--${size}`}
        ref={dialogRef}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <header className="modal__header">
          <h2 id="modal-title" className="modal__title">{title}</h2>
          <button className="modal__close" onClick={onClose} aria-label="Close">×</button>
        </header>
        <div className="modal__body">{children}</div>
        {footer && <footer className="modal__footer">{footer}</footer>}
      </div>
    </div>
  );
};

const Toast = ({ type = "info", message, onDismiss }) => (
  <div className={`toast toast--${type}`} role="status">
    <span className="toast__message">{message}</span>
    <button className="toast__dismiss" onClick={onDismiss} aria-label="Dismiss">×</button>
  </div>
);

const Card = ({ header, footer, children, onClick, className = "", ariaLabel }) => (
  <div
    className={`card ${onClick ? "card--clickable" : ""} ${className}`}
    onClick={onClick}
    onKeyDown={onClick ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } } : undefined}
    role={onClick ? "button" : undefined}
    tabIndex={onClick ? 0 : undefined}
    aria-label={ariaLabel}
  >
    {header && <header className="card__header">{header}</header>}
    <div className="card__body">{children}</div>
    {footer && <footer className="card__footer">{footer}</footer>}
  </div>
);

const Table = ({ columns, rows, onRowClick, loading, emptyState, ariaLabel }) => {
  if (loading) return <TableSkeleton rows={5} columns={columns.length} />;
  if (!rows?.length) return emptyState || <EmptyState title="No records" />;
  return (
    <table className="table" aria-label={ariaLabel}>
      <thead>
        <tr>{columns.map((c) => <th key={c.key} scope="col" style={c.width ? { width: c.width } : undefined}>{c.label}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={row.id}
            onClick={onRowClick ? () => onRowClick(row) : undefined}
            tabIndex={onRowClick ? 0 : -1}
          >
            {columns.map((c) => <td key={c.key}>{c.render ? c.render(row) : row[c.key]}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
};

const TableSkeleton = ({ rows, columns }) => (
  <table className="table table--loading">
    <tbody>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i}>{Array.from({ length: columns }).map((_, j) => (
          <td key={j}><span className="skeleton skeleton--text" /></td>
        ))}</tr>
      ))}
    </tbody>
  </table>
);

const EmptyState = ({ icon = "📭", title, description, cta }) => (
  <div className="empty-state">
    <div className="empty-state__icon" aria-hidden="true" style={{ fontSize: 32 }}>{icon}</div>
    <h3 className="empty-state__title">{title}</h3>
    {description && <p className="empty-state__description">{description}</p>}
    {cta}
  </div>
);

const Spinner = ({ size = "md", label = "Loading" }) => (
  <span className={`spinner spinner--${size}`} role="status" aria-label={label} />
);

const Badge = ({ tone = "neutral", children }) => (
  <span className={`badge badge--${tone}`}>{children}</span>
);

const Avatar = ({ name, src, size = "md" }) => {
  const initials = (name || "?").split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase();
  return src
    ? <img className={`avatar avatar--${size}`} src={src} alt={name} />
    : <span className={`avatar avatar--${size} avatar--initials`} aria-label={name}>{initials}</span>;
};

// ─── Book-Companion-specific atoms ──────────────────────────────────

const BookCover = ({ initials, size = "md" }) => (
  <span className={`bc-cover bc-cover--${size}`} aria-hidden="true">{initials}</span>
);

const EngineChip = ({ engine, voice }) => {
  const isKokoro = engine === "kokoro";
  return (
    <span className={`bc-engine-chip ${isKokoro ? "" : "bc-engine-chip--web"}`} title={`Engine: ${engine}, voice: ${voice || ""}`}>
      <span aria-hidden="true">{isKokoro ? "◆" : "◇"}</span>
      <span>{isKokoro ? "Kokoro" : "Web Speech"}{voice ? ` · ${voice}` : ""}</span>
    </span>
  );
};

const CoverageBar = ({ done, total, ariaLabel }) => {
  const pct = total ? Math.round((done / total) * 100) : 0;
  return (
    <div className="bc-coverage-bar" role="progressbar" aria-valuenow={pct} aria-valuemin="0" aria-valuemax="100" aria-label={ariaLabel}>
      <span className="bc-coverage-bar__fill" style={{ width: `${pct}%` }} />
    </div>
  );
};

const Banner = ({ tone = "warning", icon, title, body, action, onDismiss }) => (
  <div className={`bc-banner ${tone === "info" ? "bc-banner--info" : ""}`} role={tone === "info" ? "status" : "alert"}>
    <span className="bc-banner__icon" aria-hidden="true">{icon || (tone === "info" ? "ℹ" : "⚠")}</span>
    <div className="bc-banner__body">
      {title && <strong style={{ display: "block", marginBottom: 2 }}>{title}</strong>}
      {body}
    </div>
    {action && <span className="bc-banner__action">{action}</span>}
    {onDismiss && <button className="modal__close" onClick={onDismiss} aria-label="Dismiss" style={{ fontSize: 18 }}>×</button>}
  </div>
);

const SpeedSelect = ({ value, onChange }) => (
  <label className="bc-speed-select" title="Playback speed">
    <span className="sr-only">Playback speed</span>
    <select value={value} onChange={(e) => onChange(parseFloat(e.target.value))}>
      {[0.75, 1, 1.25, 1.5, 1.75, 2].map((s) => (
        <option key={s} value={s}>{s}×</option>
      ))}
    </select>
  </label>
);

const Playbar = ({ extraControls, onClose }) => {
  const p = window.__proto.usePlayer();
  const fmt = window.__proto.fmt;
  if (!p.book_id) return null;
  return (
    <div className="bc-playbar" role="region" aria-label="Audio player">
      <button
        className="bc-playbar__play"
        onClick={() => window.__proto.player.toggle()}
        aria-label={p.is_playing ? "Pause" : "Play"}
      >
        <span aria-hidden="true">{p.is_playing ? "❚❚" : "▶"}</span>
      </button>
      <button className="bc-playbar__control" onClick={() => window.__proto.player.skipSentence(-1)} aria-label="Previous sentence">
        <span aria-hidden="true">⏮</span>
      </button>
      <button className="bc-playbar__control" onClick={() => window.__proto.player.skipSentence(1)} aria-label="Next sentence">
        <span aria-hidden="true">⏭</span>
      </button>
      <span className="bc-playbar__time">
        {fmt.duration(p.elapsed_sec)} / {fmt.duration(p.duration_sec)}
        {p.sentence_count > 0 && (
          <span style={{ marginLeft: 8, color: "var(--color-text-muted)" }}>· sentence {p.sentence_index + 1} of {p.sentence_count}</span>
        )}
      </span>
      <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 8 }}>
        <EngineChip engine={p.engine} voice={p.voice} />
        <SpeedSelect value={p.speed} onChange={(s) => window.__proto.player.setSpeed(s)} />
        {extraControls}
        <IconButton icon="✕" ariaLabel="Close player" onClick={() => { window.__proto.player.close(); onClose && onClose(); }} />
      </span>
    </div>
  );
};

const KbdShortcutsModal = () => {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const h = () => setOpen(true);
    window.addEventListener("proto:open-shortcuts", h);
    return () => window.removeEventListener("proto:open-shortcuts", h);
  }, []);
  const sc = window.__designTokens?.interaction?.shortcuts || {};
  return (
    <Modal open={open} onClose={() => setOpen(false)} title="Keyboard shortcuts">
      <table className="table">
        <tbody>
          {Object.entries(sc).map(([k, v]) => (
            <tr key={k}><td><kbd>{k}</kbd></td><td>{v}</td></tr>
          ))}
        </tbody>
      </table>
    </Modal>
  );
};

const GlobalToasts = () => {
  const list = window.__proto.useToasts();
  if (!list.length) return null;
  return (
    <div className="toast-container" role="region" aria-label="Notifications">
      {list.map((t) => (
        <Toast key={t.id} type={t.type} message={t.message} onDismiss={() => window.__proto.toast.dismiss(t.id)} />
      ))}
    </div>
  );
};

window.__protoComponents = {
  Button, IconButton, Input, Modal, Toast, Card, Table, TableSkeleton, EmptyState, Spinner, Badge, Avatar,
  BookCover, EngineChip, CoverageBar, Banner, SpeedSelect, Playbar, KbdShortcutsModal, GlobalToasts,
};
/* New variants proposed: BookCover, EngineChip, CoverageBar, Banner, SpeedSelect, Playbar, KbdShortcutsModal — flagged in COMPONENTS.md "Components proposed by /prototype". */
