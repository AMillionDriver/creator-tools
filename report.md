# Penetration Test Report

## Overview
Security review of the Creator Tools application (Flask backend with Redis rate/quota controls and static frontend). Assessment emphasized authentication/authorization, exposure of downloader functionality, and resource-abuse risks.

## Methodology
- Static code review of backend Flask routes, authentication helper, and quota enforcement.
- Review of frontend behavior to understand request patterns and exposure surface.
- Threat modeling for unauthorized access, cross-origin abuse, and resource exhaustion.

## Findings

### 1) Downloader API lacks authentication/authorization (High)
All backend routes are reachable without authentication; the `require_api_key` decorator is imported but never applied. The download endpoints (`/api/download`, `/api/process-video`, status, and file serving) therefore accept requests from any internet client, and quota tracking keys off the client IP rather than a verified identity. An attacker can freely invoke downloads, enumerate task IDs, or fetch completed files belonging to other users.

**Evidence:** Endpoints are defined without protection and identify users only by `request.remote_addr` when starting a download.【F:backend/app.py†L205-L332】 The API-key decorator exists but is unused in the route definitions.【F:backend/auth.py†L5-L23】【F:backend/app.py†L15-L16】

**Recommendation:** Require authentication on every state-changing and file-serving route (e.g., session or token with per-user quota). Apply the decorator (or equivalent) to all sensitive endpoints and reject requests that lack valid credentials.

### 2) Permissive CORS enables drive-by abuse (High)
CORS is enabled globally for all origins, and requests are simple JSON posts without CSRF defenses. Combined with the unauthenticated API, any external website can trigger downloads on behalf of a visitor’s browser, consuming server bandwidth and quota with a single embedded script.

**Evidence:** The Flask app enables CORS with no origin restrictions at startup.【F:backend/app.py†L27-L41】 The exposed endpoints accept POST requests without CSRF tokens or origin checks.【F:backend/app.py†L205-L332】

**Recommendation:** Restrict CORS to trusted origins, add CSRF protection, and require authentication headers/tokens so cross-origin requests cannot silently invoke downloader actions.

### 3) Downloader throughput enables resource exhaustion (Medium)
Each request can fetch files up to 5 GB with a one-hour subprocess timeout, and the server starts downloads immediately after minimal validation. Only three concurrent downloads are blocked via a semaphore; there are no aggregate disk/CPU caps or cleanup of completed files. Attackers can queue repeated large downloads to exhaust disk, bandwidth, and worker slots despite daily per-IP quota limits.

**Evidence:** Maximum file size and timeout are set to 5 GB and one hour, and downloads start via background threads guarded only by a 3-slot semaphore.【F:backend/app.py†L49-L195】 Quota is enforced per IP with a 15 GB daily limit, allowing repeated large requests from varied networks to bypass meaningful throttling.【F:backend/app.py†L266-L302】【F:backend/quota.py†L6-L69】

**Recommendation:** Reduce size/time limits, add global and per-account caps on concurrent tasks and storage, implement automatic cleanup of old artifacts, and tighten quota enforcement (e.g., per authenticated user with behavioral anomaly detection).

## Conclusion
The downloader remains exposed to the public internet with no authentication and permissive cross-origin access, making abuse straightforward. Locking down access control, restricting origins, and hardening resource limits are necessary to prevent unauthorized use and operational disruption.
