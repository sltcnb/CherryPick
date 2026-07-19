# Security Policy

CherryPick is a forensic acquisition tool that runs with elevated privileges
and handles sensitive data (credentials, browser history, event logs, disk
images, signing keys, upload credentials). We take security issues in it
seriously.

## Supported Versions

Only the latest commit on `main` is actively supported. There are no
maintained release branches at this time.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report it privately by opening a
[GitHub security advisory](../../security/advisories/new) on this repository,
or by contacting the maintainers directly. Include:

- A description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept code or commands, if possible)
- The affected file(s)/component(s) and, if known, the commit/version

We will acknowledge reports as soon as possible and work with you on a fix
and coordinated disclosure timeline. Please give us a reasonable amount of
time to address the issue before any public disclosure.

## Scope

Areas of particular interest for security review:

- Bundle signing and verification (`crypto.py`, `verify_bundle.py`)
- Remote upload channels (`secure_upload.py`, `remote_upload.py`,
  `fo_uploader.py`, `agent_client.py`) — TLS/mTLS handling, credential
  handling, encryption of chunked uploads
- Path handling in collectors (`collectors/`) when operating against
  attacker-controlled or malicious disk images
- Handling of secrets such as `CHERRYPICK_SIGNING_KEY`,
  `CHERRYPICK_SIGNING_KEY_HEX`, and API tokens

## Out of Scope

- Vulnerabilities that require an attacker to already have the privileges
  needed to run CherryPick as an operator (e.g. local administrator/SYSTEM)
- Issues in third-party dependencies — please report those upstream, though
  we're happy to hear about them too so we can track/patch/pin around them
