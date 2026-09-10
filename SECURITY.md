# Security policy

## Supported code

Security fixes target the current default branch. Older snapshots have no promised
backport support. This is a single-owner, self-hosted application, not a multi-user
service or an independently audited security product.

## Report a vulnerability privately

Use **Security → Report a vulnerability** on the repository hosting this project
when private reporting is enabled. Do not put credentials, private post content,
exploit instructions, or sensitive logs in a public issue.

If that option is unavailable, open an issue asking the maintainer to enable a
private reporting channel without disclosing the vulnerability. Fork maintainers
must enable private vulnerability reporting before inviting security reports.

Include the affected commit, component, impact, reproduction steps using fake
credentials, and a suggested mitigation if you have one. Maintainers will coordinate
investigation and disclosure as availability permits; there is no guaranteed SLA.

## Deployment boundaries

- Bind to loopback (the Compose default). Use an SSH tunnel or an HTTPS reverse
  proxy for remote access. Set `DASHBOARD_HTTPS=true` when using HTTPS.
- Use a unique dashboard password and random session secret. Login cookies are
  signed, HTTP-only and SameSite Strict. Mutations require CSRF tokens.
- No MFA, account recovery, per-user roles, or login rate limiting is included.
  Keep the app private; use an authenticating, rate-limiting proxy if exposing it.
- `.env` and the token cache contain secrets in plaintext on disk. File permissions
  and Git exclusions do not provide encryption. Restrict host and backup access.
- Approval prevents unintended automatic posting; it cannot verify the truth of
  generated text. Review claims and personal details before approving a draft.
- External request errors are sanitized in the UI. CLI history and scheduler output
  can contain private drafts. Do not publish unredacted logs.

## Suspected credential exposure

Revoke affected OpenAI/LinkedIn credentials at the provider and replace them locally.
Rotate the dashboard password and session secret together to invalidate existing
sessions. Recreate the containers. Remove exposed data from repository history if
it was committed; adding `.gitignore` alone does not remove past commits.

See [privacy](docs/PRIVACY.md) for where content and credentials are sent.
