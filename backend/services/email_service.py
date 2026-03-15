"""
Email service — generates a PDF from markdown and sends it via SMTP.
Configure in .env:
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=your@gmail.com
  SMTP_PASSWORD=<16-char Gmail App Password>
  EMAIL_FROM=your@gmail.com
"""
import io
import smtplib
import textwrap
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from fpdf import FPDF

from config import settings


# ── PDF generation ──────────────────────────────────────────────────────────

class _PDF(FPDF):
    def __init__(self, title: str):
        super().__init__()
        self._doc_title = title

    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(60, 60, 60)
        self.cell(0, 8, self._doc_title, align="C")
        self.ln(4)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(160, 160, 160)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")


def _render_markdown_to_pdf(pdf: _PDF, text: str) -> None:
    """Minimal markdown → fpdf2 rendering: headings, bullets, bold, plain text."""
    pdf.set_auto_page_break(auto=True, margin=15)

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        # H1
        if line.startswith("# "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(0, 7, line[2:].strip())
            pdf.ln(1)

        # H2
        elif line.startswith("## "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 6, line[3:].strip())
            pdf.set_draw_color(220, 220, 220)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)

        # H3
        elif line.startswith("### "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(70, 70, 70)
            pdf.multi_cell(0, 6, line[4:].strip())

        # H4
        elif line.startswith("#### "):
            pdf.ln(1)
            pdf.set_font("Helvetica", "BI", 10)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(0, 5, line[5:].strip())

        # Bullet / list
        elif line.startswith("- ") or line.startswith("* "):
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(60, 60, 60)
            content = line[2:].strip()
            # Strip inline bold markers for simplicity
            content = content.replace("**", "")
            pdf.multi_cell(0, 5, f"  \u2022  {content}")

        # Numbered list
        elif line and line[0].isdigit() and ". " in line[:4]:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(60, 60, 60)
            content = line.replace("**", "")
            pdf.multi_cell(0, 5, f"  {content}")

        # Horizontal rule
        elif line.startswith("---"):
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)

        # Blank line
        elif line == "":
            pdf.ln(2)

        # Plain paragraph
        else:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(60, 60, 60)
            content = line.replace("**", "")
            pdf.multi_cell(0, 5, content)


def generate_pdf(title: str, content_md: str) -> bytes:
    """Convert a markdown string to a PDF and return raw bytes."""
    pdf = _PDF(title=title)
    pdf.add_page()
    _render_markdown_to_pdf(pdf, content_md)
    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ── Email sending ────────────────────────────────────────────────────────────

def send_plan_email(
    to_addresses: List[str],
    subject: str,
    body_text: str,
    pdf_bytes: bytes,
    pdf_filename: str,
) -> None:
    """Send an email with a PDF attachment via SMTP."""
    if not settings.smtp_user or not settings.smtp_password:
        raise RuntimeError(
            "SMTP not configured. Add SMTP_USER and SMTP_PASSWORD to .env "
            "(use a Gmail App Password if you have 2FA enabled)."
        )

    msg = MIMEMultipart()
    msg["From"] = settings.email_from or settings.smtp_user
    msg["To"] = ", ".join(to_addresses)
    msg["Subject"] = subject

    msg.attach(MIMEText(body_text, "plain"))

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename=pdf_filename)
    msg.attach(attachment)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, to_addresses, msg.as_string())
