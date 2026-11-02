# Progressive landing visuals

Area: frontend · Status: active

## Purpose

Procedural three.js/GSAP visuals supply the product identity with non-WebGL and reduced-motion paths. Graphics performance remains something to measure, not infer from a successful build.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`frontend/components/moody-eye.tsx`](../../../frontend/components/moody-eye.tsx)
- [`frontend/components/brand-eye.tsx`](../../../frontend/components/brand-eye.tsx)
- [`frontend/components/ambient.tsx`](../../../frontend/components/ambient.tsx)

## How-it-works docs

- [`frontend/README.md`](../../../frontend/README.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0033](ADR-0033-progressive-eye-and-code-presentation.md) | decision | Keep visual effects optional and code presentation separate from search semantics | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Verify keyboard, reduced-motion and unavailable-WebGL paths when changing visuals.
- Keep frontend code preview claims separate from backend code retrieval.
