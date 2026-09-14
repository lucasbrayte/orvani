# Professional Catalog Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform `catalogo.html` into a polished retail storefront with an automatically rotating featured-product showcase driven by the existing `Destaque` field.

**Architecture:** Keep the existing HTML/CSS/JavaScript stack. Add pure presentation helpers to `script.js`, a catalog-only featured rotator and category strip, and catalog-scoped styling. Preserve the Sheets contract, affiliate URL safety, filters, product dialog, refresh loop and footer.

**Tech Stack:** Semantic HTML, CSS, vanilla JavaScript, Node.js built-in test runner.

**Spec:** `docs/superpowers/specs/2026-09-14-catalog-professional-redesign-design.md`

## Global Constraints
- Footer byte-for-byte unchanged.
- No backend/Sheets/LibreOffice changes.
- `Destaque = Sim` is `product.featured === true`.
- Rotation interval exactly 5000 ms.
- No new external runtime dependency.
- Existing search, filters, dialog, refresh and safe links preserved.

---

### Task 1: Pure helpers
**Files:** `script.js`, `tests/js/catalog.test.js`
- [ ] Add RED tests for featured selection, circular featured windows and category counts.
- [ ] Implement `featuredProducts`, `featuredProductWindow`, `catalogCategoryPresentation`.
- [ ] Export through `OrvaniCore`.

### Task 2: Catalog markup
**Files:** `catalogo.html`, `tests/js/catalog.test.js`
- [ ] Add featured hosts and accessible controls before results.
- [ ] Add category-strip host before filters.
- [ ] Verify footer unchanged.

### Task 3: Automatic rotation and category interaction
**Files:** `script.js`
- [ ] Render one lead + up to three secondary features.
- [ ] Rotate circularly every 5000 ms.
- [ ] Pause/resume on interaction, visibility and reduced motion.
- [ ] Reuse existing filter state for category buttons.

### Task 4: Professional styling
**Files:** `style.css`
- [ ] Add catalog storefront visual system.
- [ ] Add responsive featured composition.
- [ ] Restyle toolbar and product cards.
- [ ] Use 3 desktop / 4 wide desktop columns.
- [ ] Preserve reduced motion.

### Task 5: Verification and delivery
- [ ] `node --test tests/js/catalog.test.js`
- [ ] `git diff --check`
- [ ] footer equality verification
- [ ] commit implementation
- [ ] fast-forward main
- [ ] re-test on main
- [ ] push origin/main
- [ ] remove only redesign worktree/local branch
