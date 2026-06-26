# AGENTS.md — Benro Industries Website

## Project structure

- **Root (`good/`)** — deployable site output (edit here)
- **`benro-site/`** — original site snapshot (pre-redesign, read-only reference)
- **`benro-redesign/`** — GSD workspace with specs in `docs/`; `benro-redesign/public/` is a copy of root

All HTML is **self-contained** (inline CSS/JS, no bundler, no `package.json`). Only dependencies are image files in `assets/images/`.

## Build commands (run from root)

```sh
python build_products.py   # regenerates products/*.html from build_products.py data
python build_blog.py       # regenerates blog.html + blog/*.html from build_blog.py data
```

Edit the Python file data (not the generated HTML) when content changes — then re-run the generator.

## Pages

| File | Purpose |
|---|---|
| `index.html` | Homepage (Ph1: redesigned, ~1064 lines inline) |
| `about.html` | About + company timeline (Ph3) |
| `blog.html` | Blog listing grid |
| `blog/<slug>.html`  ×18 | Individual articles |
| `products/<slug>.html` ×6 | Technical datasheets |

## Key technical details

- **Brand color**: `--brand:#E45911` (BENRO Orange)
- **i18n**: Built-in JS object (`I18N`) switching EN/FR/AR via `data-i18n` attributes — add keys to the object when adding new text
- **No framework, no npm, no bundler** — pure HTML/CSS/JS
- **GSD tool**: `npx @opengsd/get-shit-done-redux@latest --codex --local --profile=core` (for spec-driven workflow)

## When editing

- Keep CSS variables consistent with root `:root` block
- Reuse the existing topbar/header/footer pattern (identical across all pages)
- New blog posts / product changes go in the Python generator data, not the HTML files directly
