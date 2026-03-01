# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Corsair, please report it responsibly through **GitHub Security Advisories**:

1. Go to the [Security Advisories page](https://github.com/PierreHerrada/clipper-ai/security/advisories)
2. Click **"New draft security advisory"**
3. Fill in the details of the vulnerability
4. Submit the advisory

**Do not** open a public issue for security vulnerabilities.

## Scope

The following are in scope for security reports:

- Authentication and authorization bypasses
- SQL injection, command injection, or other injection attacks
- Cross-site scripting (XSS) in the web UI
- Insecure handling of secrets or credentials
- WebSocket security issues
- Docker container escape or privilege escalation
- Exposure of sensitive data in logs or API responses

## Out of Scope

- Vulnerabilities in dependencies (report these upstream)
- Social engineering attacks
- Denial of service (DoS) attacks
- Issues that require physical access to the server

## Response Time

- **Acknowledgment:** Within 48 hours of report submission
- **Initial assessment:** Within 5 business days
- **Fix timeline:** Depends on severity, but we aim for:
  - Critical: 24-48 hours
  - High: 1 week
  - Medium: 2 weeks
  - Low: Next release cycle

## Secrets and Configuration

Secrets must never be committed to the repository. All sensitive configuration is managed through environment variables. See `.env.example` for the list of required variables and their descriptions.

If you believe a secret has been accidentally committed, please report it immediately through the security advisory process above.
