# modules_email_utils
[Back to Architecture Overview](../README.md)

## Purpose
Purpose: Email utils module.

## Key Classes
- **EmailResult** - encapsulates the result of ``send_email`` including
  success status, error message, SMTP responses and message id.

## Key Functions
- **send_email(subject, body, recipients, cfg, html, image, attachment, attachment_name, attachment_type) -> EmailResult** - Send an email or log to console if SMTP is not configured. Supports plain text, HTML, and attachments.
- **sign_token(data, secret)** -
- **verify_token(data, token, secret)** -

## Inputs and Outputs
``send_email`` returns an ``EmailResult`` with fields ``success``, ``error``,
``responses`` and ``message_id``.

## Redis Keys
None

## Dependencies
- email.message
- hashlib
- hmac
- logging
- smtplib
- typing

## SMTP Configuration

Provide SMTP settings under the `email` section of `config.json`:

- `smtp_host`
- `smtp_port`
- `smtp_user`
- `smtp_pass`
- `use_tls` or `use_ssl`
- `from_addr`

If no SMTP host is configured, emails are not sent and a log entry is written instead.
