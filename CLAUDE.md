# IO — coding conventions

## Frontend (React + TypeScript + antd + Tailwind)

- **No inline styles.** Tailwind is already configured (`tailwind.config.js`, `postcss.config.js`, `src/index.css`) — use utility classes via `className` instead of `style={{...}}`. The `io` color scale in `tailwind.config.js` maps to the brand tokens in `src/lib/brand.ts` (`io-600` = primary, `io-900` = primaryStrong). Exception: truly dynamic values Tailwind can't express as a class at build time (e.g. a chart's computed pixel height) may still use `style`.
- **Responsive by default.** Every new screen/component must hold up from mobile width up — use Tailwind's responsive prefixes (`sm:`/`md:`/`lg:`/`xl:`) rather than fixed pixel widths that break on narrow viewports. Don't ship a layout only checked at desktop width.
- **Optional chaining.** Prefer `a?.b?.c` over manual `a && a.b && a.b.c` null-guard chains, and over assuming a field exists just because a TS type says so when the runtime data (API response, seed data) may not guarantee it.
- **Mandatory loading state on every API-triggering control.** Any button, menu item, or form submit that fires an API call must show a loading state for the duration of the request and block double-submits — no fire-and-forget clicks. Use `lib/useAsyncAction.ts`'s `const [run, loading] = useAsyncAction(fn)` for a new one-off action, or a hand-rolled `useState` boolean (keyed by row/item id for per-row actions in a list/table) wired into antd's `Button loading={...}`, `Modal confirmLoading={...}`, or `Dropdown disabled={...}` + trigger `Button loading={...}`. `Modal.confirm({ onOk: async () => {...} })` already gets this for free (antd shows a spinner on its OK button whenever `onOk` returns a Promise) — no extra state needed there. This applies to every new control going forward, and existing controls should be retrofitted when touched.

## Backend (FastAPI + pymongo)

- Seed writes must be upsert-by-natural-key or tag-scoped deletes — never a blanket `delete_many({})` against a collection that can also hold real user-submitted data (see `services/seed.py`'s `_seed_core` vs `seed_hr` split).
- Never call a global SSL/TLS monkeypatch (e.g. `truststore.inject_into_ssl()`) at app startup — scope it to the specific client that needs it.
