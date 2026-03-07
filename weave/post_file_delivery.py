from __future__ import annotations

from werkzeug.utils import secure_filename


def _safe_pdf_filename(original_name):
    normalized = secure_filename(str(original_name or "document.pdf")) or "document.pdf"
    if not normalized.lower().endswith(".pdf"):
        normalized = f"{normalized}.pdf"
    return normalized


def send_download_response(row, inline_requested, send_file):
    if inline_requested and str(row["mime_type"] or "").lower() == "application/pdf":
        response = send_file(
            row["stored_path"], mimetype="application/pdf", as_attachment=False
        )
        response.headers["Content-Disposition"] = (
            f'inline; filename="{_safe_pdf_filename(row["original_name"])}"'
        )
        return response
    return send_file(
        row["stored_path"], as_attachment=True, download_name=row["original_name"]
    )


def send_uploaded_pdf_inline(full_path, original_name, send_file):
    response = send_file(full_path, mimetype="application/pdf", conditional=True)
    response.headers["Content-Disposition"] = (
        f'inline; filename="{_safe_pdf_filename(original_name)}"'
    )
    return response


def send_uploaded_file(full_path, send_file):
    return send_file(full_path, conditional=True)
