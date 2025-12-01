# Security Review

## Scope
Manual review of the current repository focusing on common web application risks such as SQL/NoSQL injection, command injection, cross-site scripting (XSS), forced redirects, and malware injection vectors.

## Observations

### Data storage and injection
* The backend does not integrate with a SQL or NoSQL database, so there are no direct SQL/NoSQL injection surfaces identified in the existing code. The primary data structure is an in-memory `download_tasks` dictionary in `backend/app.py`.

### Command execution and URL handling
* `/api/download` and `/api/process-video` accept arbitrary user URLs and pass them directly to `yt-dlp` without validating scheme or allow-listing hosts. Although the code uses `subprocess` with argument lists (mitigating direct shell injection), accepting unvalidated URLs enables **server-side request forgery (SSRF)** and access to local network/file resources supported by `yt-dlp` (e.g., `file://`, `sftp://`, `http://127.0.0.1`).
* Custom filenames submitted by clients are sanitized for path separators, but the output template still trusts the provided `format_id` and URL entirely, enabling attackers to trigger downloads of arbitrary remote content or large files.

### File serving and path safety
* `/downloads/<path:filename>` uses Flask's `send_from_directory`, which mitigates basic path traversal. However, filenames stored in `download_tasks` come from filesystem listings without content-type validation, so serving arbitrary downloaded files (including malicious executables) remains possible if an attacker can coerce the service into fetching them.

### Authentication and authorization
* All endpoints are unauthenticated. Attackers can remotely trigger downloads, poll task status, and retrieve any file present in the downloads directory. There are no rate limits or origin checks, so the service could be abused for bandwidth/compute exhaustion or as an open proxy for file retrieval.

### Client-side injection and clickjacking
* The frontend renders values returned by the backend directly into the DOM via `textContent` or `src` attributes, which avoids script injection for titles/uploader names. However, `thumbnail` is written to `img.src` without validation, allowing a remote URL chosen by the attacker (via `yt-dlp` metadata) to load arbitrary external content. There is no Content Security Policy (CSP) header enforcement to reduce clickjacking or malicious resource loading risks.

## Recommendations
* Enforce URL allow-listing (schemes and domains) before invoking `yt-dlp`; reject local-network or file-based URLs to reduce SSRF risk.
* Add authentication and request-rate limiting to download and status endpoints to prevent abuse and unauthorized file retrieval.
* Validate `thumbnail` and other media URLs or proxy them through a trusted fetcher; consider adding a strict CSP and `X-Frame-Options` to mitigate malicious resource loading and clickjacking.
* Restrict served file types or scan downloaded files before exposing them via `/downloads/<filename>` to prevent distributing malware through coerced downloads.
* Implement size/timeouts for downloads and subprocess execution to reduce resource exhaustion and potential DoS vectors.
