# Penetration Test Report

## Overview
Security assessment of the Creator Tools project with focus on network-exposed Flask backend (`backend/app.py`) and bundled frontend (`frontend/templates`, `frontend/static`). Review covered authentication, access control, sensitive data handling, and abuse resistance.

## Methodology
- Static analysis of Python backend and frontend JavaScript/HTML templates.
- Threat modeling for authentication, resource usage, and data exposure paths.
- Manual review of subprocess usage and file-serving logic.

## Findings

### 1) Authentication becomes optional when `API_KEY` is missing (High)
The `require_api_key` decorator only blocks requests if the `API_KEY` environment variable is set; otherwise it transparently allows every request. In default setups without a configured key, all protected endpoints (`/api/download`, `/api/process-video`) become publicly accessible despite appearing to require authentication. This enables unauthorized use of the downloader and bypasses quota enforcement that is keyed to the presented API key or client IP.

**Evidence:**
- Decorator returns the wrapped handler without any check when `API_KEY` is falsy.【F:backend/auth.py†L8-L22】
- API endpoints rely on that decorator for protection and still derive `user_identifier` from the API key header when present, assuming authentication happened.【F:backend/app.py†L193-L289】

**Recommendation:** Fail fast when `API_KEY` is absent (e.g., refuse to start or reject all requests), and enforce authentication consistently for every state-changing or data-returning endpoint.

### 2) API key is embedded in the rendered HTML and reused by client JavaScript (High)
The server injects the API key into a `<meta>` tag and frontend code reads it to set the `X-API-Key` header on every request. Any visitor or intermediary can view and reuse the key, defeating its purpose as a shared secret and enabling cross-origin abuse since CORS is fully enabled. Attackers can harvest the key and drive the backend to perform downloads under the victim’s quota or infrastructure.

**Evidence:**
- Template exposes the API key to the browser via a meta tag.【F:frontend/templates/index.html†L3-L36】
- Frontend script reads that meta tag and attaches the key to backend requests.【F:frontend/static/script.js†L33-L69】
- Backend enables CORS for all origins, making stolen keys usable from any site.【F:backend/app.py†L27-L41】

**Recommendation:** Treat the API key as a server-side secret—do not embed it in client assets. Require user-specific authentication (sessions or OAuth), keep secrets server-only, and restrict CORS to trusted origins.

### 3) Download service can be abused for resource exhaustion (Medium)
The backend permits downloads up to 5 GB per request with one-hour subprocess timeouts, uses in-memory rate limits, and identifies users by API key or IP. When authentication is absent or the shared key leaks, attackers can spawn many long-running `yt-dlp` processes, consuming bandwidth, disk, and CPU. The in-memory limiter and quota file offer limited protection (reset on restart, shared across users behind NAT) and CORS exposure allows drive-by abuse from other origins.

**Evidence:**
- Large file limit and extended timeout for each download task.【F:backend/app.py†L43-L117】
- Requests are rate-limited and quota-tracked only after the weak authentication layer noted above.【F:backend/app.py†L193-L289】

**Recommendation:** Enforce strong authentication first, lower the maximum file size/timeout, add server-side caps on concurrent tasks and total disk usage, and persist rate limiting/quota tracking in a hardened store (e.g., Redis) with per-account enforcement.

## Conclusion
The most critical issues are the optional authentication path and the exposed API key, which together nullify access control and enable remote abuse. Addressing these gaps and tightening resource limits will substantially harden the downloader against misuse and compromise.