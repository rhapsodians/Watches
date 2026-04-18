from __future__ import annotations
import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from watchbot.models import SearchResult

logger = logging.getLogger(__name__)


def build_subject(results: list[SearchResult], run_date: str) -> str:
    total_new = sum(len(r.new_listings) for r in results)
    exact_new = sum(
        sum(1 for l in r.new_listings if l.is_exact_ref_match)
        for r in results
    )
    parts = []
    if exact_new:
        parts.append(f"{exact_new} exact ref match{'es' if exact_new != 1 else ''}")
    if total_new:
        parts.append(f"{total_new} new listing{'s' if total_new != 1 else ''}")
    summary = " · ".join(parts) if parts else "no new listings"
    return f"[WatchBot] {run_date} — {summary}"


def send_email(html_body: str, results: list[SearchResult], smtp_cfg: dict) -> None:
    run_date = date.today().isoformat()
    subject = build_subject(results, run_date)

    smtp_user = os.environ.get("SMTP_USER", smtp_cfg.get("from_address", ""))
    smtp_pass = os.environ.get("SMTP_PASS", "")
    to_addresses = smtp_cfg.get("to_addresses", [])

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP credentials not set — skipping email.")
        return
    if not to_addresses:
        logger.warning("No recipient addresses configured — skipping email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = ", ".join(to_addresses)

    plain = _build_plain_text(results)
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    host = smtp_cfg.get("smtp_host", "smtp.gmail.com")
    port = smtp_cfg.get("smtp_port", 587)

    try:
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            if smtp_cfg.get("use_tls", True):
                server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_addresses, msg.as_string())
        logger.info("Email sent: %s", subject)
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        raise


def _build_plain_text(results: list[SearchResult]) -> str:
    lines = ["WatchBot Daily Report", "=" * 40, ""]
    for result in results:
        lines.append(f"{result.target.brand} — {result.target.model} (Ref: {result.target.reference})")
        if result.new_listings:
            for listing in result.new_listings:
                star = "★ EXACT MATCH — " if listing.is_exact_ref_match else ""
                full = " [Full Set]" if listing.has_full_set else ""
                lines.append(f"  NEW: {star}{listing.display_price}{full}")
                lines.append(f"       {listing.title}")
                lines.append(f"       {listing.url}")
        else:
            lines.append("  No new listings today.")
        if result.errors:
            lines.append(f"  Warnings: {'; '.join(result.errors)}")
        lines.append("")
    return "\n".join(lines)
