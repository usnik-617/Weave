from __future__ import annotations

import io


def test_batch_upload_accepts_multiple_images_and_returns_item_map(
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

    payload = {
        "files": [
            (io.BytesIO(png_file_bytes), "a.png", "image/png"),
            (io.BytesIO(png_file_bytes), "b.png", "image/png"),
            (io.BytesIO(png_file_bytes), "c.png", "image/png"),
        ],
        "tokens": ["t1", "t2", "t3"],
        "representative_index": "2",
    }
    response = client.post(
        f"/api/posts/{gallery_id}/files/batch",
        data=payload,
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )

    assert response.status_code in {201, 207}
    body = response.get_json() or {}
    assert body.get("success") is True
    data = body.get("data") or {}
    items = data.get("items") or []
    assert len(items) >= 3
    for item in items:
        assert int(item.get("file_id") or 0) > 0
        assert str(item.get("file_url") or "").startswith("/uploads/")


def test_batch_upload_rejects_when_file_count_exceeds_limit(
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

    files = []
    for index in range(13):
        files.append((io.BytesIO(png_file_bytes), f"{index}.png", "image/png"))

    response = client.post(
        f"/api/posts/{gallery_id}/files/batch",
        data={"files": files},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json() or {}
    assert payload.get("success") is False
    assert "최대" in str(payload.get("error") or "")
