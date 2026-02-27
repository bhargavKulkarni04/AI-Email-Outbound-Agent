
"""
Send Email Module
Sends HTML emails with responsive embedded mockup, professional signature, and CC to team.
"""

import os
import re
import base64
import html
from email.message import EmailMessage
import config


def parse_attendees(attendee_str):
    """Extracts email addresses from the 'Client Attendees' string like "['a@b.com']"."""
    if not attendee_str:
        return []
    cleaned = attendee_str.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
    return [e.strip() for e in cleaned.split(",") if "@" in e]


def text_to_html(text):
    """
    Converts plain text email body to clean HTML.
    Handles **bold**, bullet points, and links.
    """
    ALLOWED_SCHEMES = ("http://", "https://", "mailto:")
    A_RE = re.compile(
        r'<a\s+href=[\'\"](https?://[^\'\"]+|mailto:[^\'\"]+)[\'\"]\s*[^>]*>(.*?)</a>',
        re.I | re.S
    )

    anchors = []
    def _a_repl(m):
        url = m.group(1).strip()
        label = (m.group(2) or url).strip()
        if not url.lower().startswith(ALLOWED_SCHEMES):
            return html.escape(m.group(0))
        safe = f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'
        tok = f"@@A{len(anchors)}@@"
        anchors.append(safe)
        return tok
    tokenized = A_RE.sub(_a_repl, text)

    esc = html.escape(tokenized)
    esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
    esc = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', esc)

    lines = esc.splitlines()
    parts, i = [], 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*-\s+", line):
            parts.append("<ul>")
            while i < len(lines) and re.match(r"^\s*-\s+", lines[i]):
                item = re.sub(r"^\s*-\s+", "", lines[i]).strip()
                parts.append(f"<li>{item}</li>")
                i += 1
            parts.append("</ul>")
            continue
        parts.append("" if not line.strip() else f"<p>{line}</p>")
        i += 1
    esc = "\n".join(parts)

    for idx, a in enumerate(anchors):
        esc = esc.replace(f"@@A{idx}@@", a)

    return esc


def build_signature_html():
    """Returns the professional NoBrokerHood HTML signature block."""
    return """
    <hr>
    <p><img src="cid:siggif" alt="NoBrokerHood" width="72"></p>
    <p><strong>Bhargav Kulkarni</strong><br>
    Brand Partnerships &amp; Alliances<br>
    <a href="tel:+918618818322" style="color: #0066cc; text-decoration: none;">+91 8618818322</a> | NoBrokerHood</p>
    """


def send(gmail_service, to_emails, subject, email_body, mockup_bytes=None, cc=None):
    """
    Sends one HTML email with:
    - Responsive embedded mockup image
    - Professional signature with GIF logo
    - Attachment for the mockup as well
    - MOM is removed as per user request
    """
    try:
        body_html_content = text_to_html(email_body)

        # Build responsive HTML with embedded image
        full_html = f"""
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                .image-container {{
                    margin: 20px 0;
                    text-align: left;
                }}
                .responsive-img {{
                    max-width: 100%;
                    height: auto;
                    border-radius: 8px;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                }}
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            </style>
        </head>
        <body>
            <div>{body_html_content}</div>
            
            {"<div class='image-container'><img src='cid:mockup' class='responsive-img' alt='Brand Mockup'></div>" if mockup_bytes else ""}
            
            {build_signature_html()}
        </body>
        </html>
        """

        # Plain text fallback
        full_text = f"{email_body}\n\n--\nBhargav Kulkarni\nBrand Partnerships & Alliances\n+91 8618818322 | NoBrokerHood"

        msg = EmailMessage()
        msg["To"] = ", ".join(to_emails)
        msg["From"] = "me"
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc

        msg.set_content(full_text)
        msg.add_alternative(full_html, subtype="html")

        # Attach and embed signature GIF
        html_part = msg.get_body(preferencelist=("html",))
        if html_part and os.path.exists(config.SIGNATURE_GIF_PATH):
            with open(config.SIGNATURE_GIF_PATH, "rb") as f:
                html_part.add_related(
                    f.read(),
                    maintype="image",
                    subtype="gif",
                    cid="siggif"
                )

        # Attach and embed Mockup Image
        if mockup_bytes and html_part:
            # For embedding
            html_part.add_related(
                mockup_bytes,
                maintype="image",
                subtype="png",
                cid="mockup"
            )
            # For traditional attachment
            msg.add_attachment(
                mockup_bytes,
                maintype="image",
                subtype="png",
                filename="NBH_Brand_Mockup.png"
            )

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = gmail_service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        sent_id = result.get("id", "")
        print(f"[SENT] To: {', '.join(to_emails)} (ID: {sent_id})")
        return sent_id

    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return None
