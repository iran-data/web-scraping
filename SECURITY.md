# Security policy

## Supported versions

The project is currently pre-1.0. Security fixes are applied to the latest repository version;
older snapshots are not maintained as separate release lines.

## Reporting a vulnerability

Do not open a public issue containing credentials, cookies, session files, personal data, or a
working access-control bypass. Use the repository host's private security-advisory feature when
available. Include:

- affected version or commit;
- impacted source/component;
- reproduction steps with secrets removed;
- expected impact;
- a minimal suggested remediation, if known.

## Sensitive files

Playwright storage state may contain authorization material. Keep it under
`playwright/.auth/` or another protected path, never commit it, and never upload it as a CI
artifact. Fixtures and inspection reports must be sanitized before review.

## Scope

Security issues in this project include accidental secret disclosure, unsafe URL handling,
session leakage, dependency vulnerabilities, and behavior that bypasses access controls.
Ordinary upstream layout changes and website outages are reliability issues; report them without
including sensitive response data.
