/* Book Companion audiobook prototype — runtime
 * Self-contained: hash router, mock store w/ pub-sub, mockApi w/ latency,
 * inline-data fallback for file://. No external imports.
 */
(() => {
  const proto = (window.__proto = {});

  // ── 1. Latency ─────────────────────────────────────────────────────────
  proto.simulateLatency = (min = 200, max = 800) =>
    new Promise((r) => setTimeout(r, min + Math.random() * (max - min)));

  // ── 2. Error injection ────────────────────────────────────────────────
  const params = new URLSearchParams(window.location.search);
  proto.injectErrors = (params.get("inject-errors") || "").split(",").filter(Boolean);

  // ── 3. Store ──────────────────────────────────────────────────────────
  const data = {};
  const subs = new Map();
  function emit(entity) {
    (subs.get(entity) || new Set()).forEach((cb) => cb());
  }
  proto.store = {
    seed(entity, records) { data[entity] = records.slice(); emit(entity); },
    list(entity) { return data[entity] || []; },
    get(entity, id) { return (data[entity] || []).find((r) => r.id === id); },
    where(entity, pred) { return (data[entity] || []).filter(pred); },
    create(entity, record) {
      data[entity] = data[entity] || [];
      const id = record.id || `${entity}-${Date.now()}`;
      const full = { ...record, id, createdAt: new Date().toISOString() };
      data[entity].push(full); emit(entity); return full;
    },
    update(entity, id, patch) {
      const i = (data[entity] || []).findIndex((r) => r.id === id);
      if (i < 0) return null;
      data[entity][i] = { ...data[entity][i], ...patch }; emit(entity);
      return data[entity][i];
    },
    remove(entity, id) {
      data[entity] = (data[entity] || []).filter((r) => r.id !== id); emit(entity);
    },
    subscribe(entity, cb) {
      if (!subs.has(entity)) subs.set(entity, new Set());
      subs.get(entity).add(cb);
      return () => subs.get(entity).delete(cb);
    },
  };

  // ── 4. Mock data loader (fetch + inline fallback) ─────────────────────
  proto.loadMockData = async () => {
    const meta = document.querySelector('meta[name="mock-entities"]');
    const entities = (meta?.content || "").split(",").map((s) => s.trim()).filter(Boolean);
    for (const entity of entities) {
      let records;
      try {
        const res = await fetch(`./assets/${entity}.json`);
        if (!res.ok) throw new Error("not ok");
        records = await res.json();
      } catch {
        const inline = document.getElementById(`mock-${entity}`);
        records = inline ? JSON.parse(inline.textContent) : [];
      }
      proto.store.seed(entity, records);
    }
  };

  // ── 5. Mock API ──────────────────────────────────────────────────────
  // Default REST handlers; feature-specific handlers added below.
  function defaultHandle(method, path, body) {
    if (proto.injectErrors.includes(path)) throw new Error(`Injected: ${path}`);
    const m = path.match(/^\/([^\/]+)(?:\/([^\/]+))?$/);
    if (!m) return null;
    const [, entity, id] = m;
    if (method === "GET" && !id) return proto.store.list(entity);
    if (method === "GET" && id) return proto.store.get(entity, id);
    if (method === "POST") return proto.store.create(entity, body);
    if (method === "PUT" && id) return proto.store.update(entity, id, body);
    if (method === "DELETE" && id) { proto.store.remove(entity, id); return { ok: true }; }
    return null;
  }
  const customHandlers = [];
  proto.registerHandler = (method, pattern, fn) => customHandlers.push({ method, pattern, fn });
  function handle(method, path, body) {
    for (const h of customHandlers) {
      if (h.method !== method) continue;
      const params = matchPattern(h.pattern, path);
      if (params) return h.fn(params, body);
    }
    const r = defaultHandle(method, path, body);
    if (r === null) throw new Error(`No handler for ${method} ${path}`);
    return r;
  }
  function matchPattern(pattern, path) {
    const pp = pattern.split("/"), tp = path.split("/");
    if (pp.length !== tp.length) return null;
    const params = {};
    for (let i = 0; i < pp.length; i++) {
      if (pp[i].startsWith(":")) params[pp[i].slice(1)] = decodeURIComponent(tp[i]);
      else if (pp[i] !== tp[i]) return null;
    }
    return params;
  }
  proto.mockApi = {
    async get(path) { await proto.simulateLatency(); return handle("GET", path); },
    async post(path, body) { await proto.simulateLatency(); return handle("POST", path, body); },
    async put(path, body) { await proto.simulateLatency(); return handle("PUT", path, body); },
    async delete(path) { await proto.simulateLatency(); return handle("DELETE", path); },
  };

  // ── 6. Audio playback simulator ───────────────────────────────────────
  // Centralized so every screen sees the same state.
  const playerState = {
    book_id: null,
    section_id: null,
    sentence_index: 0,
    sentence_count: 0,
    is_playing: false,
    speed: 1.0,
    engine: "kokoro",
    voice: "Bella",
    elapsed_sec: 0,
    duration_sec: 0,
    listeners: new Set(),
    timer: null,
  };
  function playerEmit() { playerState.listeners.forEach((cb) => cb()); }
  proto.player = {
    state: playerState,
    subscribe(cb) { playerState.listeners.add(cb); return () => playerState.listeners.delete(cb); },
    load(opts) {
      Object.assign(playerState, opts, { sentence_index: opts.sentence_index || 0, elapsed_sec: 0, is_playing: false });
      if (playerState.timer) clearInterval(playerState.timer);
      playerEmit();
    },
    play() {
      if (playerState.is_playing) return;
      playerState.is_playing = true;
      playerState.timer = setInterval(() => {
        playerState.elapsed_sec += 1 * playerState.speed;
        // sentence advance ~ every (duration/sentence_count) sec
        const perSentence = playerState.duration_sec && playerState.sentence_count
          ? playerState.duration_sec / playerState.sentence_count : 8;
        playerState.sentence_index = Math.min(
          playerState.sentence_count - 1,
          Math.floor(playerState.elapsed_sec / perSentence)
        );
        if (playerState.elapsed_sec >= playerState.duration_sec) {
          playerState.is_playing = false;
          clearInterval(playerState.timer);
          playerState.timer = null;
        }
        playerEmit();
      }, 1000);
      playerEmit();
    },
    pause() {
      playerState.is_playing = false;
      if (playerState.timer) { clearInterval(playerState.timer); playerState.timer = null; }
      playerEmit();
    },
    toggle() { playerState.is_playing ? proto.player.pause() : proto.player.play(); },
    skipSentence(delta) {
      playerState.sentence_index = Math.max(0, Math.min(playerState.sentence_count - 1, playerState.sentence_index + delta));
      const perSentence = playerState.duration_sec && playerState.sentence_count
        ? playerState.duration_sec / playerState.sentence_count : 8;
      playerState.elapsed_sec = playerState.sentence_index * perSentence;
      playerEmit();
    },
    setSpeed(s) { playerState.speed = s; playerEmit(); },
    setEngine(engine, voice) { playerState.engine = engine; if (voice) playerState.voice = voice; playerEmit(); },
    close() { proto.player.pause(); playerState.book_id = null; playerState.section_id = null; playerEmit(); },
  };

  // ── 7. Toast queue ────────────────────────────────────────────────────
  const toasts = [];
  const toastListeners = new Set();
  proto.toast = {
    push({ type = "info", message, ms = 4000 }) {
      const id = `t-${Date.now()}-${Math.random()}`;
      toasts.push({ id, type, message, ms });
      toastListeners.forEach((cb) => cb());
      setTimeout(() => proto.toast.dismiss(id), ms);
      return id;
    },
    dismiss(id) {
      const i = toasts.findIndex((t) => t.id === id);
      if (i >= 0) { toasts.splice(i, 1); toastListeners.forEach((cb) => cb()); }
    },
    list: () => toasts.slice(),
    subscribe: (cb) => { toastListeners.add(cb); return () => toastListeners.delete(cb); },
  };

  // ── 8. Hash router ────────────────────────────────────────────────────
  function parseRoute() {
    const hash = window.location.hash.slice(1) || "/";
    return { path: hash };
  }
  proto.navigate = (path) => { window.location.hash = path; };
  proto.useRoute = () => {
    const [route, setRoute] = React.useState(parseRoute());
    React.useEffect(() => {
      const onChange = () => setRoute(parseRoute());
      window.addEventListener("hashchange", onChange);
      return () => window.removeEventListener("hashchange", onChange);
    }, []);
    return { ...route, navigate: proto.navigate };
  };
  proto.useStore = (entity) => {
    const [, force] = React.useReducer((x) => x + 1, 0);
    React.useEffect(() => proto.store.subscribe(entity, force), [entity]);
    return proto.store.list(entity);
  };
  proto.usePlayer = () => {
    const [, force] = React.useReducer((x) => x + 1, 0);
    React.useEffect(() => proto.player.subscribe(force), []);
    return playerState;
  };
  proto.useToasts = () => {
    const [, force] = React.useReducer((x) => x + 1, 0);
    React.useEffect(() => proto.toast.subscribe(force), []);
    return toasts;
  };

  // ── 9. Global keyboard shortcuts (per DESIGN.md x-interaction.shortcuts) ──
  window.addEventListener("keydown", (e) => {
    if (e.target && /input|textarea|select/i.test(e.target.tagName)) return;
    if (e.key === " " && playerState.book_id) { e.preventDefault(); proto.player.toggle(); }
    if (e.key === "ArrowLeft" && playerState.book_id) { e.preventDefault(); proto.player.skipSentence(-1); }
    if (e.key === "ArrowRight" && playerState.book_id) { e.preventDefault(); proto.player.skipSentence(1); }
    if (e.key === "?") { e.preventDefault(); window.dispatchEvent(new CustomEvent("proto:open-shortcuts")); }
    if (e.key === "/") { const s = document.querySelector('input[type="search"]'); if (s) { e.preventDefault(); s.focus(); } }
  });

  // ── 10. Helpers exposed for screens ────────────────────────────────
  proto.fmt = {
    duration(sec) {
      if (!sec || sec < 0) return "0:00";
      const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
      return `${m}:${String(s).padStart(2, "0")}`;
    },
    minutes(sec) { return Math.round(sec / 60); },
    size(mb) {
      if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
      if (mb >= 1) return `${Math.round(mb)} MB`;
      return `${(mb * 1024).toFixed(0)} KB`;
    },
    sentenceIndex(i, count) { return `sentence ${i + 1} of ${count}`; },
  };

  // ── 11. Feature-specific mock handlers ─────────────────────────────
  proto.registerHandler("POST", "/audio/generate", (_, body) => {
    // body: { book_id, content, voice_id, engine }
    const job = proto.store.create("audio_jobs", {
      book_id: body.book_id,
      status: "RUNNING",
      progress: 0,
      sections_total: body.sections_total || 10,
      sections_completed: 0,
      sections_failed: 0,
      engine: body.engine || "kokoro",
      voice: body.voice || "af_bella",
      started_at: new Date().toISOString(),
      eta_seconds: 600,
      error_message: null,
    });
    // Animate progress
    const tick = setInterval(() => {
      const j = proto.store.get("audio_jobs", job.id);
      if (!j || j.status !== "RUNNING") { clearInterval(tick); return; }
      const next = Math.min(j.sections_total, j.sections_completed + 1);
      const status = next >= j.sections_total ? "COMPLETED" : "RUNNING";
      proto.store.update("audio_jobs", job.id, {
        sections_completed: next,
        progress: next / j.sections_total,
        status,
        eta_seconds: Math.max(0, (j.sections_total - next) * 30),
      });
      if (status === "COMPLETED") {
        clearInterval(tick);
        proto.toast.push({ type: "success", message: `Audio generated for ${j.sections_total} sections.` });
      }
    }, 1500);
    return job;
  });
  proto.registerHandler("POST", "/audio/regenerate-stale", (_, body) => {
    const sections = proto.store.where("sections", (s) => s.book_id === body.book_id && s.is_stale);
    sections.forEach((s) => proto.store.update("sections", s.id, { is_stale: false, audio_status: "complete" }));
    return { regenerated: sections.length };
  });
  proto.registerHandler("DELETE", "/books/:id/audio", (params) => {
    const sections = proto.store.where("sections", (s) => s.book_id === params.id);
    sections.forEach((s) => proto.store.update("sections", s.id, {
      audio_status: "none", audio_duration_sec: 0, audio_size_mb: 0, is_stale: false, engine: null, voice: null,
    }));
    proto.store.update("books", params.id, { audio_sections_count: 0, audio_total_min: 0, audio_size_mb: 0, has_stale_audio: false });
    return { deleted: sections.length };
  });
  proto.registerHandler("DELETE", "/sections/:id/audio", (params) => {
    proto.store.update("sections", params.id, { audio_status: "none", audio_duration_sec: 0, audio_size_mb: 0, engine: null, voice: null });
    return { ok: true };
  });

  // ── 12. Bootstrap ─────────────────────────────────────────────────
  proto.ready = proto.loadMockData();
})();
