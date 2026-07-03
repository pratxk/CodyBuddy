"""Baked premium dark-theme design-system scaffold (Phase 0).

A FIXED set of hand-written React + plain-CSS files shipped verbatim into every
premium build. They are NEVER LLM-generated, so they cost zero output tokens and
render the same polished CRM/HRMS/ERP look every time. Views compose these
primitives from ``../ui``; the planner can re-theme an app purely by overriding
the ``:root`` CSS variables in ``/styles.css`` — primitives reference
``var(--...)`` and never raw hex.

Exports:
    PREMIUM_SCAFFOLD_FILES: dict[str, str]   Sandpack-style /path -> source map.
    premium_primitives_cheatsheet() -> str   Frozen prop API injected into every
                                             later view-generation call.

No graph/prompt/API wiring lives here — that is a later phase.
"""

# ── /styles.css ─────────────────────────────────────────────────────────────
# Dark design tokens + a small component layer (so hover/active/focus states are
# real CSS, and hex literals live ONLY here — everything else uses var(--...)).
_STYLES_CSS = """\
:root {
  /* base surfaces (slate-950 stack) */
  --bg: #020617;
  --surface: #0f172a;
  --surface-2: #172033;
  --surface-hover: #1c2842;
  --border: #1e293b;
  --border-strong: #2b3a52;

  /* brand + semantic accents */
  --primary: #F97316;
  --primary-strong: #ea6407;
  --primary-soft: rgba(249, 115, 22, 0.14);
  --success: #14b8a6;
  --success-strong: #0d9488;
  --success-soft: rgba(20, 184, 166, 0.14);
  --success-border: rgba(20, 184, 166, 0.3);
  --warning: #f59e0b;
  --warning-strong: #d97706;
  --warning-soft: rgba(245, 158, 11, 0.14);
  --warning-border: rgba(245, 158, 11, 0.3);
  --danger: #f43f5e;
  --danger-strong: #e11d48;
  --danger-soft: rgba(244, 63, 94, 0.14);
  --danger-border: rgba(244, 63, 94, 0.3);
  --danger-border-strong: rgba(244, 63, 94, 0.4);
  --danger-bg-hover: rgba(244, 63, 94, 0.22);
  --info: #38bdf8;
  --info-soft: rgba(56, 189, 248, 0.14);
  --info-border: rgba(56, 189, 248, 0.3);
  --primary-border: rgba(249, 115, 22, 0.35);

  /* text */
  --text: #e2e8f0;
  --text-strong: #f8fafc;
  --muted: #94a3b8;
  --muted-2: #64748b;

  /* radius */
  --radius-sm: 8px;
  --radius: 12px;
  --radius-lg: 16px;
  --radius-pill: 999px;

  /* shadows (tuned for dark surfaces) */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.4);
  --shadow-md: 0 6px 20px rgba(2, 6, 23, 0.55);
  --shadow-lg: 0 18px 48px rgba(2, 6, 23, 0.65);
  --ring: 0 0 0 3px rgba(249, 115, 22, 0.35);

  /* spacing scale (4px base) */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;

  /* typography */
  --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "JetBrains Mono", "Fira Code", Menlo,
    Consolas, monospace;

  --sidebar-w: 264px;
  --topbar-h: 64px;
}

* { box-sizing: border-box; }

html, body, #root {
  height: 100%;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

h1, h2, h3, h4 { color: var(--text-strong); margin: 0; font-weight: 650; letter-spacing: -0.01em; }
p { margin: 0; }
a { color: var(--primary); text-decoration: none; }
button { font-family: inherit; }

/* number columns read better with tabular figures */
.tnum { font-variant-numeric: tabular-nums; }

::selection { background: var(--primary-soft); color: var(--text-strong); }

/* dark scrollbars */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: var(--radius-pill);
  border: 2px solid var(--bg);
}
::-webkit-scrollbar-thumb:hover { background: var(--muted-2); }

:focus { outline: none; }
:focus-visible {
  outline: none;
  box-shadow: var(--ring);
  border-radius: var(--radius-sm);
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes toastIn {
  from { opacity: 0; transform: translateX(16px) scale(0.98); }
  to { opacity: 1; transform: translateX(0) scale(1); }
}
@keyframes overlayIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes modalIn {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }
}

/* ── App shell ─────────────────────────────────────────────── */
/* Correct dashboard layout: a pinned Topbar ROW on top, then a
   [sidebar | scrollable-main] ROW that fills the rest of the viewport.
   Only .app-main scrolls; the topbar and sidebar stay put. */
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}
.app-shell-topbar { flex: none; z-index: 30; }
.app-shell-body {
  flex: 1;
  display: grid;
  grid-template-columns: var(--sidebar-w) 1fr;
  min-height: 0;
}
.app-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow-y: auto;
}
.app-content {
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  animation: fadeInUp 0.4s ease both;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: var(--space-4);
}

/* ── Sidebar ───────────────────────────────────────────────── */
.sidebar {
  background: linear-gradient(180deg, var(--surface) 0%, var(--bg) 140%);
  border-right: 1px solid var(--border);
  padding: var(--space-5) var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  height: 100%;
  min-height: 0;
  overflow-y: auto;
}
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3) var(--space-5);
}
.sidebar-brand-mark {
  width: 34px; height: 34px;
  border-radius: 10px;
  display: grid; place-items: center;
  background: linear-gradient(135deg, var(--primary), var(--primary-strong));
  color: var(--text-strong);
  box-shadow: var(--shadow-sm);
  flex: none;
}
.sidebar-brand-name { font-weight: 700; color: var(--text-strong); font-size: 15px; letter-spacing: -0.01em; }
.sidebar-brand-sub { font-size: 11px; color: var(--muted-2); text-transform: uppercase; letter-spacing: 0.08em; }
.sidebar-heading {
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--muted-2); padding: var(--space-3) var(--space-3) var(--space-2); font-weight: 600;
}
.sidebar-nav { display: flex; flex-direction: column; gap: 2px; }
.sidebar-item {
  display: flex; align-items: center; gap: var(--space-3);
  width: 100%;
  padding: var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  text-align: left;
  font-size: 13.5px;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.sidebar-item:hover { background: var(--surface-2); color: var(--text); }
.sidebar-item.active {
  background: var(--primary-soft);
  color: var(--text-strong);
  border-color: var(--primary-border);
}
.sidebar-item.active .sidebar-step {
  background: var(--primary);
  color: var(--text-strong);
  border-color: transparent;
}
.sidebar-step {
  flex: none;
  width: 24px; height: 24px;
  border-radius: 7px;
  display: grid; place-items: center;
  font-size: 11px; font-weight: 700;
  background: var(--surface-2);
  color: var(--muted);
  border: 1px solid var(--border);
}
.sidebar-item-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sidebar-item-icon { display: inline-flex; }
.sidebar-footer { margin-top: auto; padding: var(--space-4) var(--space-3) var(--space-2); color: var(--muted-2); font-size: 12px; }

/* ── Topbar ────────────────────────────────────────────────── */
.topbar {
  height: var(--topbar-h);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: 0 var(--space-6);
  border-bottom: 1px solid var(--border);
  background: rgba(15, 23, 42, 0.72);
  backdrop-filter: blur(10px);
}
.topbar-titles { display: flex; flex-direction: column; min-width: 0; }
.topbar-eyebrow { font-size: 11px; text-transform: uppercase; letter-spacing: 0.09em; color: var(--muted-2); }
.topbar-title { font-size: 17px; font-weight: 650; color: var(--text-strong); }
.topbar-spacer { flex: 1; }
.topbar-search {
  display: flex; align-items: center; gap: var(--space-2);
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  padding: var(--space-2) var(--space-4);
  color: var(--muted);
  min-width: 200px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.topbar-search:focus-within { border-color: var(--primary); box-shadow: var(--ring); }
.topbar-search input {
  border: none; background: transparent; color: var(--text);
  outline: none; width: 100%; font-size: 13px;
}
.topbar-search input::placeholder { color: var(--muted-2); }
.topbar-avatar {
  width: 38px; height: 38px; border-radius: var(--radius-pill);
  display: grid; place-items: center;
  background: linear-gradient(135deg, var(--surface-2), var(--surface-hover));
  border: 1px solid var(--border-strong);
  color: var(--text-strong); font-weight: 650; font-size: 13px; cursor: pointer;
}

/* ── Card ──────────────────────────────────────────────────── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}
.card-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-5) var(--space-3);
}
.card-title { font-size: 15px; font-weight: 650; color: var(--text-strong); }
.card-subtitle { font-size: 12.5px; color: var(--muted); margin-top: 2px; }
.card-actions { display: flex; gap: var(--space-2); flex: none; }
.card-body { padding: var(--space-3) var(--space-5) var(--space-5); }
.card-body-flush { padding: 0; }

/* ── KPIStat ───────────────────────────────────────────────── */
.kpi {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: var(--space-5);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  transition: transform 0.18s ease, border-color 0.18s ease;
}
.kpi:hover { transform: translateY(-2px); border-color: var(--border-strong); }
.kpi-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.kpi-label { font-size: 12.5px; color: var(--muted); font-weight: 500; }
.kpi-icon {
  width: 34px; height: 34px; border-radius: 9px;
  display: grid; place-items: center;
  background: var(--primary-soft); color: var(--primary); flex: none;
}
.kpi-value { font-size: 28px; font-weight: 700; color: var(--text-strong); margin-top: var(--space-3); letter-spacing: -0.02em; }
.kpi-delta { display: inline-flex; align-items: center; gap: 4px; font-size: 12.5px; font-weight: 600; margin-top: var(--space-2); }
.kpi-delta.up { color: var(--success); }
.kpi-delta.down { color: var(--danger); }
.kpi-delta.flat { color: var(--muted); }
.kpi-delta-note { color: var(--muted-2); font-weight: 500; }
.kpi-spark { position: absolute; right: 0; bottom: 0; left: 0; height: 42px; opacity: 0.9; }

/* ── ChartCard / chart containment ─────────────────────────── */
/* A hard-bounded frame so recharts (which grows to fill its parent) can never
   expand unbounded and blow out the page. width:100% + a fixed height set
   inline by <ChartCard>; the min-height:0 lets ResponsiveContainer shrink. */
.chart-frame {
  position: relative;
  width: 100%;
  min-width: 0;
  min-height: 0;
}
/* Backstop: bound the recharts container even if a chart is placed outside a
   ChartCard, so a missing/auto height can't stretch the layout. */
.recharts-responsive-container {
  width: 100% !important;
  max-width: 100%;
  min-width: 0;
  max-height: 420px;
}

/* ── DataTable ─────────────────────────────────────────────── */
.dt { display: flex; flex-direction: column; }
.dt-toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border);
}
.dt-toolbar-title { font-size: 14px; font-weight: 650; color: var(--text-strong); }
.dt-search {
  display: flex; align-items: center; gap: var(--space-2);
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  padding: var(--space-2) var(--space-3);
  color: var(--muted); min-width: 200px;
}
.dt-search:focus-within { border-color: var(--primary); box-shadow: var(--ring); }
.dt-search input { border: none; background: transparent; color: var(--text); outline: none; width: 100%; font-size: 13px; }
.dt-search input::placeholder { color: var(--muted-2); }
.dt-scroll { overflow-x: auto; }
.dt-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.dt-table thead th {
  position: sticky; top: 0;
  text-align: left;
  padding: var(--space-3) var(--space-5);
  color: var(--muted); font-weight: 600; font-size: 11.5px;
  text-transform: uppercase; letter-spacing: 0.05em;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.dt-table th.sortable { cursor: pointer; user-select: none; }
.dt-table th.sortable:hover { color: var(--text); }
.dt-th-inner { display: inline-flex; align-items: center; gap: 6px; }
.dt-sort-icon { opacity: 0.55; display: inline-flex; }
.dt-sort-icon.on { opacity: 1; color: var(--primary); }
.dt-table td {
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border);
  color: var(--text);
  vertical-align: middle;
}
.dt-table tbody tr { transition: background 0.12s ease; }
.dt-table tbody tr:hover { background: var(--surface-2); }
.dt-table td.right, .dt-table th.right { text-align: right; }
.dt-table td.center, .dt-table th.center { text-align: center; }
.dt-empty { padding: var(--space-10) var(--space-5); text-align: center; color: var(--muted); }
.dt-empty-title { color: var(--text); font-weight: 600; margin-top: var(--space-3); }
.dt-empty-sub { font-size: 12.5px; margin-top: 4px; }
.dt-footer { padding: var(--space-3) var(--space-5); color: var(--muted-2); font-size: 12px; border-top: 1px solid var(--border); }

/* ── Badge ─────────────────────────────────────────────────── */
.badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  font-size: 11.5px; font-weight: 600; line-height: 1.5;
  border: 1px solid transparent;
  white-space: nowrap;
}
.badge::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.badge.neutral { color: var(--muted); background: var(--surface-2); border-color: var(--border); }
.badge.pending { color: var(--warning); background: var(--warning-soft); border-color: var(--warning-border); }
.badge.in-progress { color: var(--info); background: var(--info-soft); border-color: var(--info-border); }
.badge.approved, .badge.success { color: var(--success); background: var(--success-soft); border-color: var(--success-border); }
.badge.rejected, .badge.danger { color: var(--danger); background: var(--danger-soft); border-color: var(--danger-border); }
.badge.warning { color: var(--warning); background: var(--warning-soft); border-color: var(--warning-border); }

/* ── Button ────────────────────────────────────────────────── */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  font-size: 13px; font-weight: 600;
  border: 1px solid transparent;
  cursor: pointer;
  transition: transform 0.12s ease, background 0.15s ease, border-color 0.15s ease, opacity 0.15s ease;
  white-space: nowrap;
}
.btn:active { transform: translateY(1px); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
.btn-primary {
  background: linear-gradient(135deg, var(--primary), var(--primary-strong));
  color: var(--text-strong);
  box-shadow: var(--shadow-sm);
}
.btn-primary:hover:not(:disabled) { filter: brightness(1.06); }
.btn-ghost { background: transparent; color: var(--text); border-color: var(--border-strong); }
.btn-ghost:hover:not(:disabled) { background: var(--surface-2); border-color: var(--muted-2); }
.btn-danger { background: var(--danger-soft); color: var(--danger); border-color: var(--danger-border-strong); }
.btn-danger:hover:not(:disabled) { background: var(--danger-bg-hover); }
.btn-sm { padding: 5px var(--space-3); font-size: 12px; }
.btn-icon { padding: var(--space-2); }

/* ── Tabs ──────────────────────────────────────────────────── */
.tabs-list {
  display: inline-flex; gap: 2px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 3px;
}
.tab {
  border: none; background: transparent; cursor: pointer;
  padding: var(--space-2) var(--space-4);
  border-radius: 7px;
  color: var(--muted); font-size: 13px; font-weight: 600;
  transition: background 0.15s ease, color 0.15s ease;
}
.tab:hover { color: var(--text); }
.tab.active { background: var(--surface); color: var(--text-strong); box-shadow: var(--shadow-sm); }
.tabs-panel { margin-top: var(--space-4); animation: fadeInUp 0.25s ease both; }

/* ── Toast ─────────────────────────────────────────────────── */
.toast-host {
  position: fixed; right: var(--space-6); bottom: var(--space-6);
  display: flex; flex-direction: column; gap: var(--space-3);
  z-index: 1000; max-width: 360px;
}
.toast {
  display: flex; align-items: flex-start; gap: var(--space-3);
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-left: 3px solid var(--muted-2);
  border-radius: var(--radius-sm);
  padding: var(--space-3) var(--space-4);
  box-shadow: var(--shadow-lg);
  animation: toastIn 0.24s ease both;
}
.toast.success { border-left-color: var(--success); }
.toast.error { border-left-color: var(--danger); }
.toast.info { border-left-color: var(--info); }
.toast-icon { flex: none; margin-top: 1px; }
.toast.success .toast-icon { color: var(--success); }
.toast.error .toast-icon { color: var(--danger); }
.toast.info .toast-icon { color: var(--info); }
.toast-body { min-width: 0; }
.toast-title { font-size: 13px; font-weight: 650; color: var(--text-strong); }
.toast-msg { font-size: 12.5px; color: var(--muted); margin-top: 1px; }
.toast-close { border: none; background: transparent; color: var(--muted-2); cursor: pointer; padding: 2px; margin-left: auto; }
.toast-close:hover { color: var(--text); }

/* ── ProgressBar ───────────────────────────────────────────── */
.progress { display: flex; flex-direction: column; gap: var(--space-2); }
.progress-head { display: flex; align-items: center; justify-content: space-between; }
.progress-label { font-size: 12.5px; color: var(--muted); font-weight: 500; }
.progress-value { font-size: 12.5px; color: var(--text-strong); font-weight: 650; }
.progress-track { height: 8px; background: var(--surface-2); border-radius: var(--radius-pill); overflow: hidden; border: 1px solid var(--border); }
.progress-fill { height: 100%; border-radius: var(--radius-pill); background: linear-gradient(90deg, var(--primary), var(--primary-strong)); transition: width 0.5s cubic-bezier(0.22, 1, 0.36, 1); }
.progress-fill.success { background: linear-gradient(90deg, var(--success), var(--success-strong)); }
.progress-fill.warning { background: linear-gradient(90deg, var(--warning), var(--warning-strong)); }
.progress-fill.danger { background: linear-gradient(90deg, var(--danger), var(--danger-strong)); }

/* ── Modal ─────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(2, 6, 23, 0.66);
  backdrop-filter: blur(4px);
  display: grid; place-items: center;
  padding: var(--space-6);
  z-index: 900;
  animation: overlayIn 0.2s ease both;
}
.modal {
  width: 100%; max-width: 520px;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  animation: modalIn 0.24s ease both;
  max-height: calc(100vh - var(--space-10));
  display: flex; flex-direction: column;
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between; gap: var(--space-4);
  padding: var(--space-5) var(--space-5) var(--space-4);
  border-bottom: 1px solid var(--border);
}
.modal-title { font-size: 16px; font-weight: 650; color: var(--text-strong); }
.modal-close { border: none; background: transparent; color: var(--muted); cursor: pointer; padding: 4px; border-radius: 7px; }
.modal-close:hover { background: var(--surface-2); color: var(--text); }
.modal-body { padding: var(--space-5); overflow-y: auto; color: var(--text); }
.modal-footer { display: flex; justify-content: flex-end; gap: var(--space-3); padding: var(--space-4) var(--space-5); border-top: 1px solid var(--border); }

/* ── Responsive ────────────────────────────────────────────── */
@media (max-width: 860px) {
  .app-shell { height: auto; min-height: 100vh; min-height: 100dvh; overflow: visible; }
  .app-shell-body { grid-template-columns: 1fr; }
  .app-main { overflow-y: visible; }
  .sidebar {
    height: auto; overflow-y: visible;
    flex-direction: row; flex-wrap: wrap; align-items: center;
    border-right: none; border-bottom: 1px solid var(--border);
  }
  .sidebar-brand { padding: var(--space-2) var(--space-3); }
  .sidebar-heading { display: none; }
  .sidebar-nav { flex-direction: row; flex-wrap: wrap; }
  .sidebar-item { width: auto; }
  .sidebar-item-label { display: none; }
  .sidebar-footer { display: none; }
  .app-content { padding: var(--space-4); }
  .topbar { padding: 0 var(--space-4); }
  .topbar-search { min-width: 0; }
}
@media (max-width: 560px) {
  .kpi-grid { grid-template-columns: 1fr 1fr; }
  .topbar-search { display: none; }
}
"""

# ── /lib/format.js ──────────────────────────────────────────────────────────
_LIB_FORMAT = """\
// Small pure formatting helpers shared by every generated view.

export function currency(value, code = "USD", opts = {}) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: code,
    maximumFractionDigits: opts.decimals ?? 0,
    ...opts,
  }).format(n);
}

export function pct(value, decimals = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return `${n.toFixed(decimals)}%`;
}

export function date(value, opts = { month: "short", day: "numeric", year: "numeric" }) {
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return "--";
  return new Intl.DateTimeFormat("en-US", opts).format(d);
}

// Tiny classnames helper (clsx-lite): joins truthy strings, skips falsy,
// and flattens { className: boolean } maps.
export function classNames(...parts) {
  const out = [];
  for (const part of parts) {
    if (!part) continue;
    if (typeof part === "string") out.push(part);
    else if (typeof part === "object") {
      for (const [key, on] of Object.entries(part)) if (on) out.push(key);
    }
  }
  return out.join(" ");
}
"""

# ── /ui/Card.js ─────────────────────────────────────────────────────────────
_UI_CARD = """\
import { classNames } from "../lib/format";

// Surface container. Optional title/subtitle header + right-aligned actions slot.
// Pass `flush` to remove body padding (e.g. when wrapping a full-bleed table).
export default function Card({ title, subtitle, actions, children, className, flush = false }) {
  const hasHeader = title || subtitle || actions;
  return (
    <section className={classNames("card", className)}>
      {hasHeader && (
        <header className="card-header">
          <div>
            {title && <div className="card-title">{title}</div>}
            {subtitle && <div className="card-subtitle">{subtitle}</div>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      <div className={classNames("card-body", { "card-body-flush": flush })}>{children}</div>
    </section>
  );
}
"""

# ── /ui/Badge.js ────────────────────────────────────────────────────────────
_UI_BADGE = """\
import { classNames } from "../lib/format";

// Status pill. `variant` maps a workflow status to token colors.
const VARIANTS = {
  pending: "pending",
  "in-progress": "in-progress",
  approved: "approved",
  rejected: "rejected",
  success: "success",
  warning: "warning",
  danger: "danger",
  neutral: "neutral",
};

// Accepts "In Progress" | "in_progress" | "in-progress" and normalizes it.
function normalize(variant) {
  const key = String(variant || "neutral").toLowerCase().replace(/[\\s_]+/g, "-");
  return VARIANTS[key] || "neutral";
}

export default function Badge({ variant = "neutral", children }) {
  const v = normalize(variant);
  return <span className={classNames("badge", v)}>{children ?? variant}</span>;
}
"""

# ── /ui/Button.js ───────────────────────────────────────────────────────────
_UI_BUTTON = """\
import { classNames } from "../lib/format";

// variant: "primary" (gradient) | "ghost" | "danger". `icon` is a lucide element.
export default function Button({
  variant = "primary",
  size = "md",
  icon = null,
  onClick,
  disabled = false,
  type = "button",
  className,
  children,
  ...rest
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={classNames(
        "btn",
        `btn-${variant}`,
        { "btn-sm": size === "sm", "btn-icon": !children && icon },
        className
      )}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}
"""

# ── /ui/KPIStat.js ──────────────────────────────────────────────────────────
_UI_KPISTAT = """\
import { useId } from "react";
import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import { ResponsiveContainer, AreaChart, Area } from "recharts";
import { classNames } from "../lib/format";

// KPI card: label + big value + optional delta/trend + optional sparkline.
// props:
//   label (string), value (string|number), delta (string, e.g. "+12.4%"),
//   trend ("up"|"down"|"flat"), icon (lucide element), note (string),
//   spark (number[] — renders a token-colored area sparkline)
export default function KPIStat({ label, value, delta, trend = "flat", icon = null, note, spark }) {
  const gradId = useId();
  const TrendIcon = trend === "up" ? ArrowUpRight : trend === "down" ? ArrowDownRight : Minus;
  const sparkData = Array.isArray(spark) ? spark.map((v, i) => ({ i, v })) : null;
  return (
    <div className="kpi">
      <div className="kpi-head">
        <span className="kpi-label">{label}</span>
        {icon && <span className="kpi-icon">{icon}</span>}
      </div>
      <div className="kpi-value tnum">{value}</div>
      {(delta || note) && (
        <div className={classNames("kpi-delta", trend)}>
          {delta && <TrendIcon size={15} />}
          {delta && <span>{delta}</span>}
          {note && <span className="kpi-delta-note">{note}</span>}
        </div>
      )}
      {sparkData && sparkData.length > 1 && (
        <div className="kpi-spark">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparkData} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="v"
                stroke="var(--primary)"
                strokeWidth={2}
                fill={`url(#${gradId})`}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
"""

# ── /ui/DataTable.js ────────────────────────────────────────────────────────
_UI_DATATABLE = """\
import { useMemo, useState } from "react";
import { Search, ChevronUp, ChevronDown, Inbox } from "lucide-react";
import { classNames } from "../lib/format";

// Client-side data table with search + sortable headers + empty state.
// columns: [{ key, label, sortable?, align?("left"|"right"|"center"), render?(value,row) }]
// rows: array of objects. searchable defaults true; searchKeys defaults to column keys.
export default function DataTable({
  columns = [],
  rows = [],
  title,
  searchable = true,
  searchKeys,
  emptyTitle = "No records found",
  emptyMessage = "Try adjusting your search or filters.",
}) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState({ key: null, dir: "asc" });

  const keys = useMemo(() => searchKeys || columns.map((c) => c.key), [searchKeys, columns]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) =>
      keys.some((k) => String(row[k] ?? "").toLowerCase().includes(q))
    );
  }, [rows, query, keys]);

  const sorted = useMemo(() => {
    if (!sort.key) return filtered;
    const copy = [...filtered];
    copy.sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      let cmp;
      if (typeof av === "number" && typeof bv === "number") cmp = av - bv;
      else cmp = String(av ?? "").localeCompare(String(bv ?? ""), undefined, { numeric: true });
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [filtered, sort]);

  function toggleSort(col) {
    if (!col.sortable) return;
    setSort((s) =>
      s.key === col.key
        ? { key: col.key, dir: s.dir === "asc" ? "desc" : "asc" }
        : { key: col.key, dir: "asc" }
    );
  }

  return (
    <div className="dt">
      {(title || searchable) && (
        <div className="dt-toolbar">
          <div className="dt-toolbar-title">{title}</div>
          {searchable && (
            <label className="dt-search">
              <Search size={15} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search..."
                aria-label="Search table"
              />
            </label>
          )}
        </div>
      )}
      <div className="dt-scroll">
        <table className="dt-table">
          <thead>
            <tr>
              {columns.map((col) => {
                const active = sort.key === col.key;
                return (
                  <th
                    key={col.key}
                    className={classNames(col.align, { sortable: col.sortable })}
                    onClick={() => toggleSort(col)}
                    aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                  >
                    <span className="dt-th-inner">
                      {col.label}
                      {col.sortable && (
                        <span className={classNames("dt-sort-icon", { on: active })}>
                          {active && sort.dir === "desc" ? (
                            <ChevronDown size={13} />
                          ) : (
                            <ChevronUp size={13} />
                          )}
                        </span>
                      )}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={columns.length}>
                  <div className="dt-empty">
                    <Inbox size={26} />
                    <div className="dt-empty-title">{emptyTitle}</div>
                    <div className="dt-empty-sub">{emptyMessage}</div>
                  </div>
                </td>
              </tr>
            ) : (
              sorted.map((row, ri) => (
                <tr key={row.id ?? ri}>
                  {columns.map((col) => (
                    <td key={col.key} className={col.align}>
                      {col.render ? col.render(row[col.key], row) : row[col.key]}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="dt-footer tnum">
        {sorted.length} of {rows.length} {rows.length === 1 ? "record" : "records"}
      </div>
    </div>
  );
}
"""

# ── /ui/icon.js ─────────────────────────────────────────────────────────────
# Robust lucide-icon resolver. Accepts EITHER a rendered lucide element
# (<Users/>) OR a STRING NAME ("Users"). A string is looked up in the full
# lucide-react namespace and rendered; unknown names fall back to a default
# glyph — the raw string is NEVER rendered as text (that was the sidebar bug).
_UI_ICON = """\
import { createElement, isValidElement } from "react";
import * as LucideIcons from "lucide-react";

const FALLBACK = LucideIcons.Circle;

// resolveIcon(icon, size?) -> a rendered lucide element (or null when icon is
// falsy). `icon` may be a lucide element, a component, or a name string like
// "Users" / "file-text" / "trending-up" (case/kebab tolerant).
export function resolveIcon(icon, size = 16) {
  if (icon == null || icon === false) return null;
  if (isValidElement(icon)) return icon;
  if (typeof icon === "function") return createElement(icon, { size });
  if (typeof icon === "string") {
    const pascal = icon
      .trim()
      .replace(/[-_\\s]+(.)?/g, (_, c) => (c ? c.toUpperCase() : ""))
      .replace(/^(.)/, (_, c) => c.toUpperCase());
    const Ico = LucideIcons[icon] || LucideIcons[pascal] || FALLBACK;
    return createElement(Ico, { size });
  }
  return createElement(FALLBACK, { size });
}
"""

# ── /ui/Sidebar.js ──────────────────────────────────────────────────────────
_UI_SIDEBAR = """\
import { classNames } from "../lib/format";
import { resolveIcon } from "./icon";

// Vertical workflow-step navigation.
// props:
//   brand (string), brandSub (string), heading (string),
//   items: [{ id, label, icon? }]  — icon may be a lucide element OR a lucide
//     NAME STRING ("Users", "FileText", "trending-up"); it is resolved to a real
//     icon and NEVER rendered as raw text,
//   activeId, onSelect(id), footer (node)
export default function Sidebar({
  brand = "Workflow",
  brandSub = "Studio",
  heading = "Workflow steps",
  items = [],
  activeId,
  onSelect,
  footer,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-brand-mark">{brand.slice(0, 1).toUpperCase()}</span>
        <div>
          <div className="sidebar-brand-name">{brand}</div>
          <div className="sidebar-brand-sub">{brandSub}</div>
        </div>
      </div>
      {heading && <div className="sidebar-heading">{heading}</div>}
      <nav className="sidebar-nav">
        {items.map((item, index) => {
          const icon = resolveIcon(item.icon, 16);
          return (
            <button
              key={item.id}
              type="button"
              className={classNames("sidebar-item", { active: item.id === activeId })}
              aria-current={item.id === activeId ? "page" : undefined}
              onClick={() => onSelect && onSelect(item.id)}
            >
              <span className="sidebar-step">{index + 1}</span>
              {icon && <span className="sidebar-item-icon">{icon}</span>}
              <span className="sidebar-item-label">{item.label}</span>
            </button>
          );
        })}
      </nav>
      {footer && <div className="sidebar-footer">{footer}</div>}
    </aside>
  );
}
"""

# ── /ui/Topbar.js ───────────────────────────────────────────────────────────
_UI_TOPBAR = """\
import { Search } from "lucide-react";

// Sticky top bar: eyebrow + current step title, optional search, avatar/actions.
// props: eyebrow, title, search (bool), searchValue, onSearch(value),
//        user ({ name }), actions (node)
export default function Topbar({
  eyebrow = "",
  title = "",
  search = true,
  searchValue = "",
  onSearch,
  user,
  actions,
}) {
  const initials = user?.name
    ? user.name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()
    : "U";
  return (
    <header className="topbar">
      <div className="topbar-titles">
        {eyebrow && <span className="topbar-eyebrow">{eyebrow}</span>}
        <span className="topbar-title">{title}</span>
      </div>
      <div className="topbar-spacer" />
      {search && (
        <label className="topbar-search">
          <Search size={15} />
          <input
            value={searchValue}
            onChange={(e) => onSearch && onSearch(e.target.value)}
            placeholder="Search..."
            aria-label="Global search"
          />
        </label>
      )}
      {actions}
      <div className="topbar-avatar" title={user?.name || "Account"}>
        {initials}
      </div>
    </header>
  );
}
"""

# ── /ui/Tabs.js ─────────────────────────────────────────────────────────────
_UI_TABS = """\
import { useState } from "react";
import { classNames } from "../lib/format";

// In-view tab switcher (self-managed useState, or controlled via value/onChange).
// tabs: [{ id, label, content?(node) }]. If a tab has `content`, the active
// panel renders automatically; otherwise render your own via onChange.
export default function Tabs({ tabs = [], defaultId, value, onChange }) {
  const [internal, setInternal] = useState(defaultId ?? tabs[0]?.id);
  const activeId = value !== undefined ? value : internal;

  function select(id) {
    if (value === undefined) setInternal(id);
    onChange && onChange(id);
  }

  const active = tabs.find((t) => t.id === activeId);
  return (
    <div>
      <div className="tabs-list" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            type="button"
            aria-selected={tab.id === activeId}
            className={classNames("tab", { active: tab.id === activeId })}
            onClick={() => select(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {active?.content !== undefined && <div className="tabs-panel">{active.content}</div>}
    </div>
  );
}
"""

# ── /ui/Toast.js ────────────────────────────────────────────────────────────
# Module-level store so useToast() and <ToastHost/> share state WITHOUT a
# provider — generated apps just drop <ToastHost/> once in /App.js.
_UI_TOAST = """\
import { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";

let _toasts = [];
const _listeners = new Set();
let _seq = 0;

function emit() {
  for (const l of _listeners) l(_toasts);
}

function push(type, title, message, duration = 3500) {
  const id = ++_seq;
  _toasts = [..._toasts, { id, type, title, message }];
  emit();
  if (duration > 0) setTimeout(() => dismiss(id), duration);
  return id;
}

function dismiss(id) {
  _toasts = _toasts.filter((t) => t.id !== id);
  emit();
}

// Stable API — safe to call from any component/handler.
export function useToast() {
  return {
    success: (title, message) => push("success", title, message),
    error: (title, message) => push("error", title, message),
    info: (title, message) => push("info", title, message),
    show: push,
    dismiss,
  };
}

const ICONS = { success: CheckCircle2, error: AlertCircle, info: Info };

export function ToastHost() {
  const [items, setItems] = useState(_toasts);
  useEffect(() => {
    const listener = (next) => setItems(next);
    _listeners.add(listener);
    setItems(_toasts);
    return () => _listeners.delete(listener);
  }, []);

  return (
    <div className="toast-host" role="region" aria-live="polite" aria-label="Notifications">
      {items.map((t) => {
        const Icon = ICONS[t.type] || Info;
        return (
          <div key={t.id} className={`toast ${t.type}`}>
            <span className="toast-icon"><Icon size={18} /></span>
            <div className="toast-body">
              {t.title && <div className="toast-title">{t.title}</div>}
              {t.message && <div className="toast-msg">{t.message}</div>}
            </div>
            <button className="toast-close" onClick={() => dismiss(t.id)} aria-label="Dismiss">
              <X size={15} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default ToastHost;
"""

# ── /ui/ProgressBar.js ──────────────────────────────────────────────────────
_UI_PROGRESSBAR = """\
import { classNames } from "../lib/format";

// Labeled progress bar. value 0-100. variant: "primary"|"success"|"warning"|"danger".
export default function ProgressBar({ value = 0, label, variant = "primary", showValue = true }) {
  const pctVal = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className="progress">
      {(label || showValue) && (
        <div className="progress-head">
          {label && <span className="progress-label">{label}</span>}
          {showValue && <span className="progress-value tnum">{Math.round(pctVal)}%</span>}
        </div>
      )}
      <div
        className="progress-track"
        role="progressbar"
        aria-valuenow={Math.round(pctVal)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label || "Progress"}
      >
        <div className={classNames("progress-fill", variant)} style={{ width: `${pctVal}%` }} />
      </div>
    </div>
  );
}
"""

# ── /ui/Modal.js ────────────────────────────────────────────────────────────
_UI_MODAL = """\
import { useEffect, useRef } from "react";
import { X } from "lucide-react";

// Accessible-ish overlay dialog. Closes on ESC + overlay click; best-effort
// focus of the panel on open. props: open, onClose, title, children, footer.
export default function Modal({ open, onClose, title, children, footer }) {
  const panelRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    function onKey(e) {
      if (e.key === "Escape") onClose && onClose();
    }
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (panelRef.current) panelRef.current.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={() => onClose && onClose()}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title || "Dialog"}
        tabIndex={-1}
        ref={panelRef}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="modal-header">
          <div className="modal-title">{title}</div>
          <button className="modal-close" onClick={() => onClose && onClose()} aria-label="Close dialog">
            <X size={18} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
"""

# ── /ui/AppShell.js ─────────────────────────────────────────────────────────
# The CORRECT dashboard layout, baked so the coder can't get it wrong:
#   ┌───────────────── Topbar (pinned, full width) ─────────────────┐
#   ├──────────┬────────────────────────────────────────────────────┤
#   │ Sidebar  │  scrollable main content (children)                 │
#   └──────────┴────────────────────────────────────────────────────┘
# The topbar is ALWAYS on top; the sidebar is a fixed-width left column; only the
# main area scrolls. Compose it in /App.js — never hand-roll this layout.
_UI_APPSHELL = """\
// Full-height app layout: fixed Topbar on top, Sidebar on the left, scrollable
// main content on the right. Pass rendered elements as props/children.
//   <AppShell topbar={<Topbar .../>} sidebar={<Sidebar .../>}>
//     {activeViewContent}
//   </AppShell>
export default function AppShell({ topbar, sidebar, children }) {
  return (
    <div className="app-shell">
      {topbar && <div className="app-shell-topbar">{topbar}</div>}
      <div className="app-shell-body">
        {sidebar}
        <main className="app-main">
          <div className="app-content">{children}</div>
        </main>
      </div>
    </div>
  );
}
"""

# ── /ui/ChartCard.js ────────────────────────────────────────────────────────
# Card wrapper that gives recharts a FIXED, bounded height so a chart can never
# expand unbounded and blow out the layout. Put a single <ResponsiveContainer
# width="100%" height="100%"> (or any recharts element) as the child.
_UI_CHARTCARD = """\
import Card from "./Card";

// Chart container with a hard height cap. Wrap ANY recharts chart in this so it
// stays contained. Give the chart <ResponsiveContainer width="100%" height="100%">;
// the fixed-height wrapper here bounds it. props: title, subtitle, actions,
// height (px, default 280), className, children.
export default function ChartCard({
  title,
  subtitle,
  actions,
  height = 280,
  className,
  children,
}) {
  return (
    <Card title={title} subtitle={subtitle} actions={actions} className={className}>
      <div className="chart-frame" style={{ height }}>
        {children}
      </div>
    </Card>
  );
}
"""

# ── /ui/index.js (barrel) ───────────────────────────────────────────────────
_UI_INDEX = """\
export { default as AppShell } from "./AppShell";
export { default as Card } from "./Card";
export { default as ChartCard } from "./ChartCard";
export { default as KPIStat } from "./KPIStat";
export { default as DataTable } from "./DataTable";
export { default as Badge } from "./Badge";
export { default as Button } from "./Button";
export { default as Sidebar } from "./Sidebar";
export { default as Topbar } from "./Topbar";
export { default as Tabs } from "./Tabs";
export { default as ProgressBar } from "./ProgressBar";
export { default as Modal } from "./Modal";
export { default as Toast, ToastHost, useToast } from "./Toast";
export { resolveIcon } from "./icon";
"""

# ── /package.json ───────────────────────────────────────────────────────────
# The baked kit ALWAYS imports lucide-react + recharts, so declare them up front
# (never rely on backfill — a refine/repair that re-emits a slim manifest would
# otherwise drop them → DependencyNotFoundError even though the /ui files need them).
_PACKAGE_JSON = """\
{
  "name": "premium-dashboard",
  "version": "1.0.0",
  "main": "/index.js",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lucide-react": "^0.460.0",
    "recharts": "^2.15.0"
  }
}
"""

# The premium kit cannot render without these — guaranteed on every premium
# generate / refine / repair so the deps can never be silently dropped.
PREMIUM_REQUIRED_DEPS: dict[str, str] = {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lucide-react": "^0.460.0",
    "recharts": "^2.15.0",
}

PREMIUM_SCAFFOLD_FILES: dict[str, str] = {
    "/styles.css": _STYLES_CSS,
    "/lib/format.js": _LIB_FORMAT,
    "/ui/icon.js": _UI_ICON,
    "/ui/AppShell.js": _UI_APPSHELL,
    "/ui/ChartCard.js": _UI_CHARTCARD,
    "/ui/Card.js": _UI_CARD,
    "/ui/KPIStat.js": _UI_KPISTAT,
    "/ui/DataTable.js": _UI_DATATABLE,
    "/ui/Badge.js": _UI_BADGE,
    "/ui/Button.js": _UI_BUTTON,
    "/ui/Sidebar.js": _UI_SIDEBAR,
    "/ui/Topbar.js": _UI_TOPBAR,
    "/ui/Tabs.js": _UI_TABS,
    "/ui/Toast.js": _UI_TOAST,
    "/ui/ProgressBar.js": _UI_PROGRESSBAR,
    "/ui/Modal.js": _UI_MODAL,
    "/ui/index.js": _UI_INDEX,
    "/package.json": _PACKAGE_JSON,
}


_CHEATSHEET = """\
PREMIUM PRIMITIVE KIT — import from "../ui" (data from "../data/mock", styles auto-loaded).
NEVER redefine these; compose them. All colors come from /styles.css tokens (var(--...)).

import { AppShell, Card, ChartCard, KPIStat, DataTable, Badge, Button, Sidebar,
         Topbar, Tabs, ProgressBar, Modal, ToastHost, useToast } from "../ui";

AppShell  (LAYOUT — use in /App.js so the topbar is ALWAYS on top, sidebar left, main scrolls)
  props: topbar?:node, sidebar?:node, children
  <AppShell topbar={<Topbar .../>} sidebar={<Sidebar .../>}>{activeViewContent}</AppShell>

Card
  props: title?:string, subtitle?:string, actions?:node, flush?:bool, className?:string, children
  <Card title="Applications" subtitle="This week" actions={<Button size="sm">Export</Button>}>...</Card>

ChartCard  (ALWAYS wrap a recharts chart in this — it bounds the height so charts never overflow)
  props: title?:string, subtitle?:string, actions?:node, height?:number=280, className?:string, children
  give the chart <ResponsiveContainer width="100%" height="100%">…</ResponsiveContainer>
  <ChartCard title="Volume" height={280}>
    <ResponsiveContainer width="100%" height="100%"><AreaChart data={rows}>…</AreaChart></ResponsiveContainer>
  </ChartCard>

KPIStat
  props: label:string (req), value:string|number (req), delta?:string, trend?:"up"|"down"|"flat",
         icon?:lucideElement, note?:string, spark?:number[]
  <KPIStat label="Approved" value="1,284" delta="+12.4%" trend="up" spark={[4,6,5,9,12]} />

DataTable
  props: columns:[{key,label,sortable?,align?:"left"|"right"|"center",render?(value,row)}] (req),
         rows:object[] (req), title?:string, searchable?:bool=true, searchKeys?:string[],
         emptyTitle?:string, emptyMessage?:string  — built-in search + client sort + empty state
  <DataTable title="Loans" columns={cols} rows={rows} />

Badge
  props: variant:"pending"|"in-progress"|"approved"|"rejected"|"success"|"warning"|"danger"|"neutral", children?
  <Badge variant="approved">Approved</Badge>

Button
  props: variant?:"primary"|"ghost"|"danger"=primary, size?:"md"|"sm", icon?:lucideElement,
         onClick?, disabled?:bool, type?:string, children
  <Button variant="primary" icon={<Check size={15}/>} onClick={approve}>Approve</Button>

Sidebar
  props: brand?:string, brandSub?:string, heading?:string,
         items:[{id,label,icon?}] (req), activeId (req), onSelect(id) (req), footer?:node
    icon accepts a LUCIDE NAME STRING ("Users","FileText","TrendingUp") OR a lucide element —
    a string is resolved to the real icon (never rendered as text). Pass the plan's icon string directly.
  <Sidebar brand="LoanFlow" items={[{id:"intake",label:"Intake",icon:"Users"}]} activeId={view} onSelect={setView} />

Topbar
  props: eyebrow?:string, title?:string, search?:bool=true, searchValue?:string,
         onSearch?(value), user?:{name}, actions?:node
  <Topbar eyebrow="Step 2" title="Underwriting" user={{name:"Ada Lovelace"}} />

Tabs
  props: tabs:[{id,label,content?:node}] (req), defaultId?, value?, onChange?(id)  — self-managed useState
  <Tabs tabs={[{id:"a",label:"Open",content:<div/>}]} />

ProgressBar
  props: value:number 0-100 (req), label?:string, variant?:"primary"|"success"|"warning"|"danger", showValue?:bool=true
  <ProgressBar label="Onboarding" value={72} variant="success" />

Modal
  props: open:bool (req), onClose:()=>void (req), title?:string, children, footer?:node  — ESC + overlay-click close
  <Modal open={open} onClose={close} title="Reject application" footer={<Button variant="danger">Confirm</Button>}>...</Modal>

Toast  (drop <ToastHost/> ONCE in /App.js; call useToast() anywhere — no provider needed)
  const toast = useToast();  // toast.success(title,msg) | toast.error(...) | toast.info(...) | toast.dismiss(id)
  <ToastHost />   // render once at the app root
"""


def premium_primitives_cheatsheet() -> str:
    """Frozen reference of every primitive's import path + exact prop signature +
    a one-line usage example. Injected into every later view-generation call so the
    coder composes the primitives correctly (drift here = runtime crashes downstream).
    """
    return _CHEATSHEET


# ── Premium-safety helpers (shared by enhance / uxmaster / oncall) ────────────
# The baked /ui kit + /lib helpers are IMPORT-CRITICAL: /App.js and every view do
# `import { ... } from "../ui"` / `"./ui"`, so if a refine or auto-repair LLM call
# omits or malforms them the whole app dies with "Could not find module './ui'".
# These helpers keep those frozen while still allowing the LLM to change the
# refinable surface (/styles.css, /App.js, /views/*, /data/mock.js, /package.json).
_FROZEN_PREFIXES = ("/ui/", "/lib/")


def is_premium_shaped(files: dict) -> bool:
    """A premium dashboard is identifiable by the baked barrel."""
    return "/ui/index.js" in (files or {})


def ensure_premium_deps(files: dict) -> dict:
    """Guarantee the premium kit's required npm deps are in /package.json.

    The frozen /ui kit ALWAYS imports lucide-react + recharts, so if a refine/
    repair LLM re-emitted a slim manifest (or ensure_dependencies ran before the
    /ui files were re-overlaid), those deps go missing → DependencyNotFoundError.
    Merge the required deps in without touching any extra deps the app added.
    """
    import json as _json

    key = "/package.json" if "/package.json" in files else "package.json"
    raw = files.get(key)
    try:
        pkg = _json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
    except (ValueError, TypeError):
        pkg = {}
    if not isinstance(pkg, dict):
        pkg = {}
    deps = pkg.get("dependencies")
    if not isinstance(deps, dict):
        deps = {}
    for name, version in PREMIUM_REQUIRED_DEPS.items():
        deps.setdefault(name, version)
    pkg.setdefault("name", "premium-dashboard")
    pkg.setdefault("version", "1.0.0")
    pkg.setdefault("main", "/index.js")
    pkg["dependencies"] = deps
    out = dict(files)
    out[key] = _json.dumps(pkg, indent=2) + "\n"
    return out


def preserve_premium_scaffold(original: dict, updated: dict) -> dict:
    """Make an LLM refine/repair safe for a premium app.

    Layer the LLM's changes over the ORIGINAL files (so nothing the LLM silently
    dropped is lost), then re-overlay the FROZEN import-critical kit (/ui/*,
    /lib/*) from the baked scaffold LAST so the barrel + primitives can never be
    clobbered, and guarantee the required deps so the kit always resolves. The
    refinable surface (styles, App, views, mock data) stays whatever the LLM
    produced, so refines still take effect.
    """
    merged = {**original, **updated}
    for path, code in PREMIUM_SCAFFOLD_FILES.items():
        if path.startswith(_FROZEN_PREFIXES):
            merged[path] = code
    return ensure_premium_deps(merged)
