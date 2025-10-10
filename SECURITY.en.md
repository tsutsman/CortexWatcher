# CortexWatcher Security Policy

## Reporting vulnerabilities
- Send reports to security@example.com (PGP encryption available on request).
- Expected response SLA — 72 hours.
- Please include reproduction steps and potential impact.

## Tokens and secrets
- Use environment variables (`.env`) only.
- Do not store tokens in the repository or logs.
- Use secret managers (Vault, AWS Secrets Manager, etc.) for production environments.

## Access control
- The Telegram bot operates with a whitelist of chat IDs.
- API endpoints with modification capabilities are protected by a token (`API_AUTH_TOKEN`).

## Dependency updates
- Run `make audit` regularly (optional) to scan for CVEs.
- Use Dependabot or Renovate for automation.

Thank you for your cooperation!
