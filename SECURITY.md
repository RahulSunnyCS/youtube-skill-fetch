# Security policy

## Reporting a vulnerability

If you believe you have found a security vulnerability in
`youtube-skill-fetch`, please report it privately.

- **Email:** add a contact address here before publishing the repo.
- **Subject line:** `[security] <short description>`
- Please do **not** open a public GitHub issue for security problems.

Include in your report:

1. A description of the issue and the impact you believe it has.
2. Steps to reproduce, or a minimal proof of concept.
3. The commit SHA or release version you tested against.
4. Your name / handle if you would like to be credited.

## What we treat as in-scope

- Code execution via untrusted input to the extraction pipeline
  (playlist URL, filenames, metadata).
- Path traversal or arbitrary file write through transcript / OCR /
  artifact handling.
- Secrets leakage in logs, artifacts, or default configuration.
- Dependency vulnerabilities with a clear exploitation path in this
  codebase.

## What we treat as out-of-scope

- Misuse of the tool by an operator (downloading content they are not
  entitled to). This is a compliance issue, not a security issue — see
  `docs/PRD.md` §12.
- Reports that depend on a malicious local user already having shell
  access to the machine running the pipeline.
- Self-XSS / social engineering scenarios.
- Issues in upstream dependencies (`yt-dlp`, `ffmpeg`, `tesseract`,
  `whisper`) without a project-specific exploitation path — please
  report those upstream.

## Our response

- We aim to acknowledge reports within **5 business days**.
- We will work with you on a coordinated disclosure timeline. The
  default window is **90 days** from acknowledgement, shortened if a
  fix ships sooner.
- We will credit reporters who want credit in the release notes.

Thank you for helping keep the project and its users safe.
