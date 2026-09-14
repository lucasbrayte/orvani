# Orvani — Professional Catalog Redesign

Date: 2026-09-14

## Goal
Redesign the Orvani catalog frontend as a polished modern storefront while preserving the current Sheets/LibreOffice data flow, affiliate-link safety, filters, product details, refresh behavior and footer.

## Scope
Frontend only: `catalogo.html`, `style.css`, `script.js`, `tests/js/catalog.test.js`.

No Google Sheets schema, backend automation, affiliate URL composition or LibreOffice changes.

The complete current footer block must remain unchanged.

## Featured Showcase
Use only products where `product.active === true && product.featured === true`.

Desktop:
- one large lead featured product;
- up to three secondary featured products.

Rotation:
- circular rotation every 5000 ms;
- every featured product becomes the lead product;
- pause on hover, focus, pointer interaction, hidden tab and reduced motion;
- previous/next controls and indicators.

If no product is featured, hide the section. Do not promote ordinary products as fallback.

## Category Strip
Build a category strip from live active products. Clicking a category must reuse the existing catalog filter state and URL synchronization.

## Search, Filters and Product Grid
Preserve existing search, type/category filters, clear action, URL sync, product dialog, refresh loop and safe affiliate links. Restyle them professionally.

Grid:
- 1 column on very narrow devices;
- 2 columns on normal phones/tablets where space allows;
- 3 columns on desktop;
- 4 columns on wide desktop.

## Technology
Keep semantic HTML, CSS and vanilla JavaScript. No Tailwind, React, Vue, Bootstrap, Swiper or new runtime dependency.

## Accessibility
Keyboard-accessible controls, meaningful labels, reduced-motion support, interaction pause and preserved dialog/focus behavior.

## Acceptance
1. Professional retail-oriented catalog.
2. `Destaque = Sim` automatically feeds the showcase.
3. Automatic 5000 ms rotation.
4. Interaction/reduced-motion pause.
5. Search, filters, dialog, refresh and affiliate URLs still work.
6. Footer unchanged.
7. No backend/schema change.
8. No new external dependency.
