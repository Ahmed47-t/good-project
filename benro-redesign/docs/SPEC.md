# SPEC — Benro Industries Homepage Redesign (Phase 1)

> Generated under the GSD (Get Shit Done) spec-driven workflow.
> Tool: `npx @opengsd/get-shit-done-redux@latest --codex --local --profile=core`

## 1. Goal
Redesign the **homepage only** of https://www.benroindustries.com so it is:
- visually modern (2026 standard), credible for a B2B HVAC&R manufacturer,
- faithful to BENRO's existing brand identity,
- fast, responsive, accessible, and interactive.

## 2. Preserved Brand Identity (extracted from live site)
| Asset | Source / value |
|---|---|
| Logo | `assets/images/benro-logo.png` (downloaded from `/wp-content/uploads/2024/10/no-bg-logo.png`) |
| Primary accent (BENRO Orange) | `#E45911` |
| Deep text / steel | `#1F2937` (derived from `#414141`) |
| Soft surface | `#FBFBFC` |
| Subtle surface | `#F3F5F7` |
| Border / divider | `#E7EBEE` |
| Secondary accent | `#0B3D91` (industrial blue — replaces unbranded purple) |
| Typography | Inter / system stack (modern, neutral, multilingual) |

## 3. Page sections (single-page, in order)
1. **Top utility bar** — phone, email, WhatsApp, language hint.
2. **Sticky header** — logo, primary nav, "Get a Quote" CTA.
3. **Hero** — headline "Air Conditioner Connecting Lines & PE Foam Manufacturer", subhead, dual CTA, trust strip, animated product visual.
4. **Trust / partner logos strip** — Daikin, Samsung, Condor, Energical, Simafe, Major Cold.
5. **Product categories grid** — 6 cards (Twin Insulated Copper, Single Insulated Copper, Twin Aluminium, PE Insulation Tubes, Copper Tubes, PE Foam) with hover lift.
6. **Why Choose BENRO** — 3 value pillars (Quality & Precision / Durability & Insulation / Reliable Supply) + image.
7. **Stats counter band** — 5 Years · 1,000,000 pcs/yr · 10 distributors · 30+ workforce, animated on scroll.
8. **Mission & Values** — split layout, values as chips.
9. **CTA banner** — "Let's Build Something Together" → Contact.
10. **Footer** — company info, quick links, contact, socials, copyright.

## 4. Interactions
- Sticky header shrinks on scroll.
- Hero headline + subhead fade-in-up on load.
- Stats counters animate from 0 when scrolled into view (IntersectionObserver).
- Product cards: lift + accent underline on hover.
- Smooth in-page scroll for nav links.
- Floating WhatsApp button (real number from current site: +213 554 250 110).
- Fully responsive: 1440 / 1024 / 768 / 390 breakpoints.

## 5. Non-functional
- No external CDN required (works inside sandboxed preview iframe).
- Inline SVG icons, system fonts as fallback (Inter via @font-face optional, but no external load needed for preview).
- Lighthouse-friendly: semantic HTML5, alt text, aria-labels, prefers-reduced-motion respected.

## 6. Deliverable for Phase 1
- `public/index.html` — single self-contained file (CSS + JS inlined) referencing local `assets/images/`.
- Preview rendered for the user.
