# IO — coding conventions

## Frontend (React + TypeScript + antd + Tailwind)

- **No inline styles.** Tailwind is already configured (`tailwind.config.js`, `postcss.config.js`, `src/index.css`) — use utility classes via `className` instead of `style={{...}}`. The `io` color scale in `tailwind.config.js` maps to the brand tokens in `src/lib/brand.ts` (`io-600` = primary, `io-900` = primaryStrong). Exception: truly dynamic values Tailwind can't express as a class at build time (e.g. a chart's computed pixel height) may still use `style`.
- **Responsive by default.** Every new screen/component must hold up from mobile width up — use Tailwind's responsive prefixes (`sm:`/`md:`/`lg:`/`xl:`) rather than fixed pixel widths that break on narrow viewports. Don't ship a layout only checked at desktop width.
- **Optional chaining.** Prefer `a?.b?.c` over manual `a && a.b && a.b.c` null-guard chains, and over assuming a field exists just because a TS type says so when the runtime data (API response, seed data) may not guarantee it.

## Backend (FastAPI + pymongo)

- Seed writes must be upsert-by-natural-key or tag-scoped deletes — never a blanket `delete_many({})` against a collection that can also hold real user-submitted data (see `services/seed.py`'s `_seed_core` vs `seed_hr` split).
- Never call a global SSL/TLS monkeypatch (e.g. `truststore.inject_into_ssl()`) at app startup — scope it to the specific client that needs it.
