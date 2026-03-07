from __future__ import annotations

import io
from datetime import datetime, timedelta

import pytest

from contract_assertions import assert_error_contract
from weave.time_utils import now_iso


def _upload_file(client, post_id, csrf_headers, filename, content, mime_type, **extra_form):
    from weave.core import clear_all_rate_limit_state

    clear_all_rate_limit_state()
    data = {
        "file": (io.BytesIO(content), filename, mime_type),
        **extra_form,
    }
    response = client.post(
        f"/api/posts/{post_id}/files",
        data=data,
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    payload = response.get_json() or {}
    assert payload.get("success") is True
    file_id = int(((payload.get("data") or {}).get("file_id") or 0))
    assert file_id > 0
    return file_id


def _first_uploaded_file_url(client, post_id):
    listed = client.get(f"/api/posts/{post_id}/files")
    assert listed.status_code == 200
    payload = listed.get_json() or {}
    assert payload.get("success") is True
    items = ((payload.get("data") or {}).get("items") or [])
    assert items
    return str(items[0].get("file_url") or "")


def test_gallery_file_is_publicly_accessible_without_login(
    client,
    create_user,
    login_as,
    csrf_headers,
    create_post_record,
    png_file_bytes,
):
    executive = create_user(role="EXECUTIVE")
    gallery_id = create_post_record(category="gallery", author_id=executive["id"])
    login_as(executive)

    _upload_file(
        client,
        gallery_id,
        csrf_headers,
        "gallery-open.png",
        png_file_bytes,
        "image/png",
    )
    file_url = _first_uploaded_file_url(client, gallery_id)

    login_as(None)
    public_get = client.get(file_url)
    public_head = client.head(file_url)

    assert public_get.status_code == 200
    assert public_head.status_code == 200


def test_notice_attachment_is_blocked_without_login(
    client,
    create_user,
    login_as,
    csrf_headers,
    create_post_record,
):
    executive = create_user(role="EXECUTIVE")
    notice_id = create_post_record(category="notice", author_id=executive["id"])
    login_as(executive)

    _upload_file(
        client,
        notice_id,
        csrf_headers,
        "notice-private.pdf",
        b"%PDF-1.4\n%%EOF\n",
        "application/pdf",
    )
    file_url = _first_uploaded_file_url(client, notice_id)

    login_as(None)
    blocked_get = client.get(file_url)

    assert blocked_get.status_code == 401
    assert_error_contract(blocked_get.get_json() or {})


def test_notice_attachment_is_forbidden_for_general_user(
    client,
    create_user,
    login_as,
    csrf_headers,
    create_post_record,
):
    executive = create_user(role="EXECUTIVE")
    notice_id = create_post_record(category="notice", author_id=executive["id"])
    login_as(executive)

    _upload_file(
        client,
        notice_id,
        csrf_headers,
        "notice-member-only.pdf",
        b"%PDF-1.4\n%%EOF\n",
        "application/pdf",
    )
    file_url = _first_uploaded_file_url(client, notice_id)

    general = create_user(role="GENERAL")
    login_as(general)
    forbidden_get = client.get(file_url)

    assert forbidden_get.status_code == 403
    assert_error_contract(forbidden_get.get_json() or {})


def test_about_image_is_publicly_accessible_without_login(
    client,
    create_user,
    login_as,
    csrf_headers,
    png_file_bytes,
):
    executive = create_user(role="EXECUTIVE")
    login_as(executive)

    upload_response = client.post(
        "/api/about/sections/image",
        data={"key": "history", "file": (io.BytesIO(png_file_bytes), "about-open.png")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201
    upload_payload = upload_response.get_json() or {}
    image_url = str(((upload_payload.get("data") or {}).get("imageUrl") or "")).strip()
    assert image_url.startswith("/uploads/")

    login_as(None)
    public_get = client.get(image_url)
    assert public_get.status_code == 200


def test_expired_file_is_blocked_for_download_and_listing(
    client,
    create_user,
    login_as,
    csrf_headers,
    create_post_record,
):
    executive = create_user(role="EXECUTIVE")
    notice_id = create_post_record(category="notice", author_id=executive["id"])
    login_as(executive)

    expired_at = (datetime.fromisoformat(now_iso()) - timedelta(minutes=10)).isoformat()
    file_id = _upload_file(
        client,
        notice_id,
        csrf_headers,
        "expired.pdf",
        b"%PDF-1.4\n%%EOF\n",
        "application/pdf",
        expires_at=expired_at,
    )

    list_response = client.get(f"/api/posts/{notice_id}/files")
    assert list_response.status_code == 200
    list_payload = list_response.get_json() or {}
    assert list_payload.get("success") is True
    assert ((list_payload.get("data") or {}).get("items") or []) == []

    download_response = client.get(f"/api/post-files/{file_id}/download")
    assert download_response.status_code == 404
    assert_error_contract(download_response.get_json() or {})


@pytest.mark.parametrize(
    ("path", "expected_status"),
    [
        ("/uploads/%2e%2e/%2e%2e/windows/win.ini", 400),
        ("/uploads/..%2F..%2Fetc%2Fpasswd", 400),
        ("/uploads/..%5C..%5Cwindows%5Cwin.ini", 400),
        ("/uploads/%252e%252e/%252e%252e/etc/passwd", 404),
        ("/uploads/%2e%2e%2f%2e%2e%2fapp.py", 400),
    ],
)
def test_path_traversal_attempt_is_rejected_with_error_contract(
    client, path, expected_status
):
    traversal = client.get(path)

    assert traversal.status_code == expected_status
    if expected_status == 400:
        assert_error_contract(traversal.get_json() or {})
