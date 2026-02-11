"""
Replit Mail - Python implementation for sending emails via OpenInt mail service.
Based on Replit Mail blueprint for Agent Stack workflows.
Emails are automatically sent to the user's verified Replit email address.
"""

import subprocess
import json
import os


def get_auth_token():
    """
    Get Replit Identity Token for authentication.
    Returns tuple of (auth_token, hostname).
    """
    hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
    if not hostname:
        raise ValueError("REPLIT_CONNECTORS_HOSTNAME environment variable not found")
    
    try:
        result = subprocess.run(
            ["replit", "identity", "create", "--audience", f"https://{hostname}"],
            capture_output=True,
            text=True,
            check=True
        )
        replit_token = result.stdout.strip()
        
        if not replit_token:
            raise ValueError("Replit Identity Token not found for repl/depl")
        
        return f"Bearer {replit_token}", hostname
    
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Failed to get Replit Identity Token: {e.stderr}")


def send_email(subject, text=None, html=None, attachments=None):
    """
    Send email via Replit Mail service.
    
    Args:
        subject (str): Email subject line
        text (str, optional): Plain text body
        html (str, optional): HTML body
        attachments (list, optional): List of attachment dicts with keys:
            - filename (str): File name
            - content (str): Base64 encoded content
            - contentType (str, optional): MIME type
            - encoding (str): One of 'base64', '7bit', 'quoted-printable', 'binary'
    
    Returns:
        dict: Response containing accepted, rejected, messageId, response
    
    Note: Emails are automatically sent to the user's verified Replit email address.
          Do NOT include 'to' or 'cc' fields.
    """
    import requests
    
    auth_token, hostname = get_auth_token()
    
    payload = {
        "subject": subject
    }
    
    if text:
        payload["text"] = text
    if html:
        payload["html"] = html
    if attachments:
        payload["attachments"] = attachments
    
    url = f"https://{hostname}/api/v2/mailer/send"
    
    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "Replit-Authentication": auth_token
        },
        json=payload
    )
    
    if not response.ok:
        try:
            error = response.json()
            raise ValueError(error.get("message", "Failed to send email"))
        except json.JSONDecodeError:
            raise ValueError(f"Failed to send email: {response.status_code} {response.text}")
    
    return response.json()


def send_dev_notes_update_notification(changes_summary=None):
    """
    Send notification email when DEV_NOTES.md is updated.
    
    Args:
        changes_summary (str, optional): Summary of changes made
    
    Returns:
        dict: Email send result or None if failed
    """
    subject = "[P.O.MFS] DEV_NOTES.md 업데이트 알림"
    
    content = """
[P.O.MFS 개발 노트 업데이트 알림]

DEV_NOTES.md 파일이 업데이트되었습니다.

"""
    if changes_summary:
        content += f"변경 내용 요약:\n{changes_summary}\n\n"
    
    content += """
관리자 페이지에서 전체 내용을 확인하세요.

---
P.O.MFS (Performance Organization AI Management For System)
"""
    
    try:
        result = send_email(
            subject=subject,
            text=content
        )
        print(f">>> DEV_NOTES 업데이트 이메일 발송 완료: {result.get('messageId', 'N/A')}")
        return result
    except Exception as e:
        print(f">>> DEV_NOTES 업데이트 이메일 발송 실패: {e}")
        return None


def markdown_to_html_email(md_content, title="P.O.MFS Report"):
    """
    Convert markdown content to nicely styled HTML for Gmail.
    
    Args:
        md_content (str): Markdown content
        title (str): Email title for header
    
    Returns:
        str: Styled HTML content
    """
    import markdown
    
    html_body = markdown.markdown(
        md_content,
        extensions=['tables', 'fenced_code', 'nl2br']
    )
    
    html_template = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 8px 8px 0 0;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600;">{title}</h1>
                            <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 14px;">P.O.MFS (Performance Organization AI Management For System)</p>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 30px;">
                            <style>
                                .email-content h1 {{ color: #1a1a2e; font-size: 22px; margin-top: 25px; margin-bottom: 15px; border-bottom: 2px solid #667eea; padding-bottom: 8px; }}
                                .email-content h2 {{ color: #16213e; font-size: 18px; margin-top: 20px; margin-bottom: 12px; }}
                                .email-content h3 {{ color: #0f3460; font-size: 16px; margin-top: 18px; margin-bottom: 10px; }}
                                .email-content p {{ color: #333; line-height: 1.6; margin: 10px 0; }}
                                .email-content table {{ border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 14px; }}
                                .email-content th {{ background-color: #667eea; color: white; padding: 12px 10px; text-align: left; font-weight: 600; }}
                                .email-content td {{ border: 1px solid #e0e0e0; padding: 10px; }}
                                .email-content tr:nth-child(even) {{ background-color: #f8f9fa; }}
                                .email-content code {{ background-color: #f4f4f4; padding: 2px 6px; border-radius: 4px; font-family: 'Monaco', 'Menlo', monospace; font-size: 13px; color: #e83e8c; }}
                                .email-content pre {{ background-color: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 6px; overflow-x: auto; font-size: 13px; }}
                                .email-content pre code {{ background-color: transparent; color: inherit; padding: 0; }}
                                .email-content ul, .email-content ol {{ padding-left: 25px; margin: 10px 0; }}
                                .email-content li {{ color: #333; line-height: 1.8; }}
                                .email-content blockquote {{ border-left: 4px solid #667eea; margin: 15px 0; padding: 10px 20px; background-color: #f8f9fa; }}
                                .email-content hr {{ border: none; border-top: 1px solid #e0e0e0; margin: 20px 0; }}
                            </style>
                            <div class="email-content">
                                {html_body}
                            </div>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 20px 30px; border-radius: 0 0 8px 8px; border-top: 1px solid #e0e0e0;">
                            <p style="color: #666; font-size: 12px; margin: 0; text-align: center;">
                                이 이메일은 P.O.MFS 시스템에서 자동으로 발송되었습니다.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''
    
    return html_template


def send_codebase_audit_report():
    """
    Send codebase audit report via email with HTML styling.
    Reads the latest audit report and sends it as formatted HTML.
    
    Returns:
        dict: Email send result or None if failed
    """
    import glob
    
    audit_files = glob.glob("docs/codebase_audit/*/CODEBASE_AUDIT_REPORT.md")
    if not audit_files:
        print(">>> 코드베이스 감사 보고서를 찾을 수 없습니다.")
        return None
    
    latest_report = sorted(audit_files)[-1]
    
    try:
        with open(latest_report, 'r', encoding='utf-8') as f:
            report_content = f.read()
    except Exception as e:
        print(f">>> 보고서 파일 읽기 실패: {e}")
        return None
    
    date_part = latest_report.split('/')[-2]
    subject = f"[P.O.MFS] 코드베이스 감사 보고서 ({date_part})"
    
    html_content = markdown_to_html_email(
        report_content, 
        title=f"코드베이스 감사 보고서 ({date_part})"
    )
    
    try:
        result = send_email(
            subject=subject,
            html=html_content,
            text=report_content
        )
        print(f">>> 코드베이스 감사 보고서 이메일 발송 완료: {result.get('messageId', 'N/A')}")
        return result
    except Exception as e:
        print(f">>> 코드베이스 감사 보고서 이메일 발송 실패: {e}")
        return None
