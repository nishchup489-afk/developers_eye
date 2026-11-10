---
id: INC-0042
title: Existing single-server ingress assumptions were unsafe for a Vercel API hop
status: resolved
date: 2026-11-10
severity: high
area: infra
feature: configuration-and-secrets
code: [deploy/Caddyfile, deploy/docker-compose.yml, frontend/lib/axios.js, backend/src/backend/api/edge_trust.py]
related: [ADR-0058, EXP-0018]
---

# INC-0042: Pre-deployment ingress trust mismatch

## Scope

This was a repository readiness defect found before deployment. No live Oracle
incident, credential compromise or attack was observed.

## Cause and expected behavior

The previous Caddy target was the colocated `web` service, and the API trusted
all forwarding peers. Moving the frontend to Vercel and exposing API ingress
changes that boundary: ordinary Caddy forwarding identifies Vercel egress rather
than the visitor, while blindly accepting a browser-supplied identity permits
quota spoofing. The overview bridge previously preserved `X-Eye-Client-IP`.
There was no independent Vercel-to-API credential.

## Resolution

Apply ADR-0058: remove colocated web, proxy to the API, require a scoped edge
credential at both Caddy and FastAPI, derive visitor identity on Vercel and
validate it after authentication, and disable broad Uvicorn proxy trust.
The existing admin service key remains a separate requirement. The Axios
interceptor never attaches this credential to GitHub/Wikipedia/browser requests.

## Verification

Backend tests cover missing/wrong/duplicate credentials, malformed/duplicate IPs,
public health, local compatibility, production configuration and independent
rate buckets. Frontend tests cover exact origin scoping, third-party/browser
exclusion, HTTPS enforcement and platform-header precedence over spoofed input.
Local Docker checks confirm Caddy denial, direct-API denial, disabled docs and
admin-key layering. Real Next.js-to-ingress validation is recorded in EXP-0018.
Cloud account, DNS, certificate and actual Vercel configuration remain pending.
