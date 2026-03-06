from __future__ import annotations

import io


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
