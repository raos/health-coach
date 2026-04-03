"""
Email service — generates a PDF from markdown and sends it via Resend.
Configure in .env:
  RESEND_API_KEY=re_...
"""
import io

import resend
from fpdf import FPDF

from config import settings


# ── Character sanitization ───────────────────────────────────────────────────

_UNICODE_REPLACEMENTS = {
    "\u2014": " - ",   # em dash —
    "\u2013": "-",     # en dash –
    "\u2018": "'",     # left single quote '
    "\u2019": "'",     # right single quote '
    "\u201c": '"',     # left double quote "
    "\u201d": '"',     # right double quote "
    "\u2026": "...",   # ellipsis …
    "\u00d7": "x",     # multiplication sign ×
    "\u2022": "-",     # bullet •
    "\u00b7": "-",     # middle dot ·
    "\u00a0": " ",     # non-breaking space
    "\u2192": "->",    # right arrow →
    "\u2190": "<-",    # left arrow ←
    "\u00b0": " deg",  # degree °
    "\u00b1": "+/-",   # plus-minus ±
    "\u00bc": "1/4",   # fraction 1/4
    "\u00bd": "1/2",   # fraction 1/2
    "\u00be": "3/4",   # fraction 3/4
}

def _sanitize(text: str) -> str:
    """Replace Unicode characters not supported by Helvetica with ASCII equivalents."""
    for char, replacement in _UNICODE_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


# ── PDF generation ───────────────────────────────────────────────────────────

class _PDF(FPDF):
    def __init__(self, title: str):
        super().__init__()
        self._doc_title = title
        self.set_margins(left=15, top=10, right=15)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(60, 60, 60)
        self.cell(self.epw, 8, self._doc_title, align="C")
        self.ln(4)
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(6)
        self.set_x(self.l_margin)

    def footer(self):
        self.set_y(-12)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(160, 160, 160)
        self.cell(self.epw, 6, f"Page {self.page_no()}", align="C")


def _render_markdown_to_pdf(pdf: _PDF, text: str) -> None:
    """Minimal markdown → fpdf2 rendering: headings, bullets, bold, plain text."""
    w = pdf.epw

    for raw_line in text.splitlines():
        pdf.set_x(pdf.l_margin)
        line = _sanitize(raw_line.rstrip())

        if line.startswith("# "):
            pdf.ln(3)
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(w, 7, line[2:].strip())
            pdf.ln(1)

        elif line.startswith("## "):
            pdf.ln(3)
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(w, 6, line[3:].strip())
            pdf.set_x(pdf.l_margin)
            pdf.set_draw_color(220, 220, 220)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(2)

        elif line.startswith("### "):
            pdf.ln(2)
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(70, 70, 70)
            pdf.multi_cell(w, 6, line[4:].strip())

        elif line.startswith("#### "):
            pdf.ln(1)
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "BI", 10)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(w, 5, line[5:].strip())

        elif line.startswith("- ") or line.startswith("* "):
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(60, 60, 60)
            content = line[2:].strip().replace("**", "")
            pdf.multi_cell(w, 5, f"  *  {content}")

        elif line and line[0].isdigit() and ". " in line[:4]:
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(w, 5, f"  {line.replace('**', '')}")

        elif line.startswith("---"):
            pdf.ln(2)
            pdf.set_x(pdf.l_margin)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(2)

        elif line == "":
            pdf.ln(2)

        else:
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(w, 5, line.replace("**", ""))


def generate_pdf(title: str, content_md: str) -> bytes:
    """Convert a markdown string to a PDF and return raw bytes."""
    pdf = _PDF(title=_sanitize(title))
    pdf.add_page()
    _render_markdown_to_pdf(pdf, content_md)
    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ── Email sending ────────────────────────────────────────────────────────────

def send_plan_email(
    to_address: str,
    subject: str,
    body_text: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str | None = None,
) -> None:
    """Send an email via Resend, optionally with a PDF attachment."""
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY not configured. Add it to your .env file.")
    if not to_address:
        raise RuntimeError("No recipient email. Set your email in Settings → Profile.")

    resend.api_key = settings.resend_api_key

    params: resend.Emails.SendParams = {
        "from": "HealthCoach <onboarding@resend.dev>",
        "to": [to_address],
        "subject": subject,
        "text": body_text,
    }
    if pdf_bytes and pdf_filename:
        params["attachments"] = [{"filename": pdf_filename, "content": list(pdf_bytes)}]
    resend.Emails.send(params)


def send_html_email(to_address: str, subject: str, html: str, cc: str = None) -> None:
    """Send an inline HTML email (no attachment) via Resend."""
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY not configured.")
    if not to_address:
        raise RuntimeError("No recipient email. Set your email in Settings → Profile.")

    resend.api_key = settings.resend_api_key
    payload = {
        "from": "HealthCoach <onboarding@resend.dev>",
        "to": [to_address],
        "subject": subject,
        "html": html,
    }
    if cc:
        payload["cc"] = [cc]
    resend.Emails.send(payload)
