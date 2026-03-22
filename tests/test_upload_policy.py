from __future__ import annotations

import io

import pytest
import weave.post_files_routes as post_files_routes

from contract_assertions import assert_error_contract


@pytest.fixture(autouse=True)
def _reset_upload_rate_limit_state(reset_rate_limit_state):
    reset_rate_limit_state()


def test_gallery_rejects_pdf_upload(
    client, create_user, login_as, csrf_headers, create_post_record
):
    executive = create_user(role="EXECUTIVE")
    gallery_id = create_post_record(category="gallery", author_id=executive["id"])
    login_as(executive)

    response = client.post(
        f"/api/posts/{gallery_id}/files",
        data={"file": (io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "gallery.pdf", "application/pdf")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json() or {}
    assert "error" in payload


def test_gallery_accepts_valid_image_upload(
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

    response = client.post(
        f"/api/posts/{gallery_id}/files",
        data={"file": (io.BytesIO(png_file_bytes), "gallery.png", "image/png")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert int((payload.get("data") or {}).get("file_id") or 0) > 0


def test_notice_accepts_pdf_upload(
    client, create_user, login_as, csrf_headers, create_post_record
):
    executive = create_user(role="EXECUTIVE")
    notice_id = create_post_record(category="notice", author_id=executive["id"])
    login_as(executive)

    response = client.post(
        f"/api/posts/{notice_id}/files",
        data={"file": (io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "notice.pdf", "application/pdf")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 201


def test_notice_accepts_image_upload(
    client,
    create_user,
    login_as,
    csrf_headers,
    create_post_record,
    png_file_bytes,
):
    executive = create_user(role="EXECUTIVE")
    notice_id = create_post_record(category="notice", author_id=executive["id"])
    login_as(executive)

    response = client.post(
        f"/api/posts/{notice_id}/files",
        data={"file": (io.BytesIO(png_file_bytes), "notice.png", "image/png")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 201


def test_invalid_file_type_returns_expected_error_json(
    client, create_user, login_as, csrf_headers, create_post_record
):
    executive = create_user(role="EXECUTIVE")
    notice_id = create_post_record(category="notice", author_id=executive["id"])
    login_as(executive)

    response = client.post(
        f"/api/posts/{notice_id}/files",
        data={
            "file": (
                io.BytesIO(b"#!/bin/sh\necho nope\n"),
                "script.sh",
                "text/plain",
            )
        },
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json() or {}
    assert payload.get("success") is False
    assert isinstance(payload.get("error"), str)
    assert payload.get("error")


def test_gallery_upload_populates_image_url_and_thumb_url(
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

    upload = client.post(
        f"/api/posts/{gallery_id}/files",
        data={"file": (io.BytesIO(png_file_bytes), "gallery-image.png", "image/png")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201

    detail = client.get(f"/api/posts/{gallery_id}")
    assert detail.status_code == 200
    detail_payload = (detail.get_json() or {}).get("data") or {}

    image_url = str(detail_payload.get("image_url") or "")
    thumb_url = str(detail_payload.get("thumb_url") or "")

    assert image_url.startswith("/uploads/")
    assert thumb_url.startswith("/uploads/")


def test_notice_pdf_download_inline_sets_pdf_headers(
    client, create_user, login_as, csrf_headers, create_post_record
):
    executive = create_user(role="EXECUTIVE")
    notice_id = create_post_record(category="notice", author_id=executive["id"])
    login_as(executive)

    upload = client.post(
        f"/api/posts/{notice_id}/files",
        data={"file": (io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "inline-check.pdf", "application/pdf")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    file_id = int((((upload.get_json() or {}).get("data") or {}).get("file_id") or 0))
    assert file_id > 0

    download = client.get(f"/api/post-files/{file_id}/download?inline=1")
    assert download.status_code == 200
    assert "application/pdf" in str(download.headers.get("Content-Type") or "")
    assert "inline" in str(download.headers.get("Content-Disposition") or "").lower()


def test_gallery_rejects_upload_when_post_total_size_exceeds_limit(
    client,
    create_user,
    login_as,
    csrf_headers,
    create_post_record,
):
    executive = create_user(role="EXECUTIVE")
    gallery_id = create_post_record(category="gallery", author_id=executive["id"])
    login_as(executive)

    original_total_limit = post_files_routes.POST_TOTAL_UPLOAD_BYTES
    original_total_limit_mb = post_files_routes.POST_TOTAL_UPLOAD_MB
    try:
        post_files_routes.POST_TOTAL_UPLOAD_BYTES = 12
        post_files_routes.POST_TOTAL_UPLOAD_MB = 0

        first_upload = client.post(
            f"/api/posts/{gallery_id}/files",
            data={"file": (io.BytesIO(b"12345678"), "one.png", "image/png")},
            headers=csrf_headers(),
            content_type="multipart/form-data",
        )
        assert first_upload.status_code == 201

        second_upload = client.post(
            f"/api/posts/{gallery_id}/files",
            data={"file": (io.BytesIO(b"12345678"), "two.png", "image/png")},
            headers=csrf_headers(),
            content_type="multipart/form-data",
        )
        assert second_upload.status_code == 400
        payload = second_upload.get_json() or {}
        assert "총 업로드 용량" in str(payload.get("error") or "")
    finally:
        post_files_routes.POST_TOTAL_UPLOAD_BYTES = original_total_limit
        post_files_routes.POST_TOTAL_UPLOAD_MB = original_total_limit_mb


@pytest.mark.parametrize(
    "role, expected_status",
    [
        (None, 401),
        ("GENERAL", 403),
        ("MEMBER", 201),
    ],
)
def test_upload_endpoint_permission_contract_by_role(
    role,
    expected_status,
    client,
    create_user,
    login_as,
    csrf_headers,
    create_post_record,
):
    author = create_user(role="EXECUTIVE")
    notice_id = create_post_record(category="notice", author_id=author["id"])

    if role is None:
        login_as(None)
    else:
        user = create_user(role=role)
        login_as(user)

    response = client.post(
        f"/api/posts/{notice_id}/files",
        data={"file": (io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "policy.pdf", "application/pdf")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )

    assert response.status_code == expected_status
    payload = response.get_json() or {}
    if expected_status == 201:
        assert payload.get("success") is True
        assert int(((payload.get("data") or {}).get("file_id") or 0)) > 0
    else:
        assert_error_contract(payload)


def test_upload_and_download_error_schema_consistency(
    client,
    create_user,
    login_as,
    csrf_headers,
    create_post_record,
    reset_rate_limit_state,
):
    login_as(None)

    upload_unauth = client.post(
        "/api/posts/99999/files",
        data={"file": (io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "x.pdf", "application/pdf")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )
    assert upload_unauth.status_code == 401
    assert_error_contract(upload_unauth.get_json() or {})

    download_unauth = client.get("/api/post-files/99999/download")
    assert download_unauth.status_code == 401
    assert_error_contract(download_unauth.get_json() or {})

    invalid_path = client.get("/uploads/../../etc/passwd")
    assert invalid_path.status_code == 400
    assert_error_contract(invalid_path.get_json() or {})

    author = create_user(role="EXECUTIVE")
    notice_id = create_post_record(category="notice", author_id=author["id"])
    general = create_user(role="GENERAL")
    login_as(general)
    reset_rate_limit_state()
    forbidden_upload = client.post(
        f"/api/posts/{notice_id}/files",
        data={"file": (io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "x.pdf", "application/pdf")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )
    assert forbidden_upload.status_code in {403, 429}
    assert_error_contract(forbidden_upload.get_json() or {})
