# Security Policy

## Supported Versions

Currently, only the latest active branch (e.g., `v3`) is fully supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| v3.x.x  | :white_check_mark: |
| v2.x.x  | :x:                |
| v1.x.x  | :x:                |

## Reporting a Vulnerability

We take the security of Medivio and its users very seriously. If you discover a vulnerability or a potential security issue in the platform, please **do not** create a public issue.

Instead, please report it privately:
1. Email your findings to the repository maintainer.
2. Include steps to reproduce the vulnerability, the potential impact, and your environment setup.

We will endeavor to respond to your report within 48 hours and provide a timeline for addressing the issue.

## Handling Credentials
- **Never commit `.env` files.**
- If you accidentally commit an API key (e.g., Gemini, Groq, Twilio, or Gmail App Password), rotate/revoke the key immediately at the provider's console.
- Do not expose your `JWT_SECRET_KEY` or `SECRET_KEY` in any public logs.
