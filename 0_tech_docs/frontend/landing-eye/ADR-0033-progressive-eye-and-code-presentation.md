---
id: ADR-0033
title: Keep visual effects optional and code presentation separate from search semantics
status: accepted
date: '2026-11-02'
area: frontend
feature: landing-eye
code:
- frontend/components/moody-eye.tsx
- frontend/components/brand-eye.tsx
- frontend/components/ambient.tsx
- frontend/components/code-preview.tsx
- frontend/components/search-experience.tsx
supersedes: null
superseded_by: null
related:
- ADR-0031
---

# ADR-0033: Keep visual effects optional and code presentation separate from search semantics

## TL;DR

Use three.js and GSAP for the visual identity while preserving reduced-motion and non-WebGL paths. Code preview helps users read pasted input; retrieval remains a backend responsibility.

## Context

The landing page moved from a static eye to procedural WebGL and pointer effects. Search still needs to work on constrained devices and for users who prefer less motion.

## Decision

The eye handles unavailable WebGL through a static fallback, renders a still frame for reduced motion, and disposes rendering resources. Ambient effects apply to fine pointers without reduced motion and do not intercept input. Search loading, error, empty and demo states stay explicit. Pasted code is displayed as code without implying exact-symbol indexing or mode routing has been delivered.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Progressive visuals around working controls | Distinct identity with fallback | Graphics and animation cost | chosen |
| Make WebGL mandatory | Uniform visual result | Excludes unsupported devices | rejected |
| Remove all visual identity | Smallest graphics cost | Loses intended product presentation | not chosen |

## Why

Visual design should enhance the search surface while leaving query entry and results usable on the simpler path.

## Consequences

- Gained: A recognizable interface with explicit accessibility fallbacks.
- Accepted limitations / tech debt: No device-level bundle, rendering or interaction benchmark is established; fallbacks alone do not prove good performance.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Reduced motion does not run the normal continuous animation.
- Unmount disposes graphics resources and listeners.
- Presentation code does not silently rewrite a query.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. WebGL change: [022b134](https://github.com/nishchup489-afk/developers_eye/commit/022b134bed134958481cee73e9b0ac27fa28f5cf).

- [`frontend/components/moody-eye.tsx`](../../../frontend/components/moody-eye.tsx)
- [`frontend/components/brand-eye.tsx`](../../../frontend/components/brand-eye.tsx)
- [`frontend/components/ambient.tsx`](../../../frontend/components/ambient.tsx)
- [`frontend/components/code-preview.tsx`](../../../frontend/components/code-preview.tsx)
- [`frontend/components/search-experience.tsx`](../../../frontend/components/search-experience.tsx)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`frontend/tests/integration.mjs`](../../../frontend/tests/integration.mjs)

## Revisit when

- Mobile interaction or rendering profiles show animation-related regressions.
- Code preview grows enough to delay query input.

## Rules for future changes

- Verify keyboard, reduced-motion and unavailable-WebGL paths when changing visuals.
- Keep frontend code preview claims separate from backend code retrieval.
