# SPEC — Phase 2 · Technical Datasheet Pages

> Generated under the GSD (Get Shit Done) spec-driven workflow.
> Tool: `npx @opengsd/get-shit-done-redux@latest --codex --local --profile=core`

## 1. Goal
- Extract every product detail from the live site (https://www.benroindustries.com).
- Give each of the **6 products** its own dedicated **Technical Datasheet** page.
- When a visitor clicks a product card on the homepage, they land on that product's full datasheet (description, benefits, technical specs, dimensions table, gallery, CTAs).

## 2. Source pages (live)
| # | Slug used in new site | Live source URL |
|---|---|---|
| 1 | `twin-insulated-copper` | https://www.benroindustries.com/twin-insulated-copper-tubes/ |
| 2 | `single-insulated-copper` | https://www.benroindustries.com/single-insulated-copper-tubes/ |
| 3 | `twin-insulated-aluminium` | https://www.benroindustries.com/twin-insulated-aluminium-tubes/ |
| 4 | `insulation-polyethylene` | https://www.benroindustries.com/insulated-polyethylene-tubes/ |
| 5 | `copper-tubes` | https://www.benroindustries.com/copper-tubes/ |
| 6 | `polyethylene-tubes` | https://www.benroindustries.com/polyethylene-tubes/ |

## 3. Sections present in every datasheet
1. **Top bar / Header / Footer** — identical components to homepage (logo, language switcher, sticky header, WhatsApp FAB).
2. **Breadcrumb** — Home › Products › *Product name*.
3. **Hero block** — product title, short pitch, two CTAs (Specifications anchor + Get Quote), large product image.
4. **Description block** — brand-voiced paragraph from the live site (faithful copy).
5. **Key benefits** — bullet list mirroring source.
6. **Technical Specifications** — structured spec groups (Copper tubing / Aluminium tubing / Insulation).
7. **Dimensions table(s)** — exact rows pulled from the live site (one product has two tables — Twin Insulation + BENRO-FLEX).
8. **Gallery** — secondary product images, including the original "Screenshot" diagrams when relevant.
9. **CTA band** — orange "Let's build something together" mirrors home.

## 4. Wiring on homepage
- Each `<article class="pcard">` becomes a clickable link to its datasheet.
- The existing `pcard__link` ("Request specs") points to the datasheet too.

## 5. Strict rules
- **Do not change any other part of the homepage design, content, identity, layout, colors, animations or behavior** (incl. languages, partners, etc.). Only the `href` of product cards changes.
- All datasheet pages share the homepage's CSS palette and components — they must look like one site.

## 6. Deliverables
- `products/<slug>.html` × 6
- Tiny shared `assets/images/products/*` (already downloaded under `/assets/images/`).
- Updated `index.html` with product card links wired to their datasheets.
