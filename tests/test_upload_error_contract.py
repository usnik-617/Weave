from __future__ import annotations

import io

import pytest

from contract_assertions import assert_error_contract


@pytest.fixture(autouse=True)
def _reset_upload_rate_limit_state(reset_rate_limit_state):
    reset_rate_limit_state()


def test_upload_file_endpoints_keep_error_response_contract(
    client, create_user, login_as, csrf_headers, create_post_record, reset_rate_limit_state
):
    login_as(None)
    unauth_upload = client.post(
        "/api/posts/99999/files",
        data={"file": (io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "x.pdf", "application/pdf")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )
    assert unauth_upload.status_code == 401
    assert_error_contract(unauth_upload.get_json() or {})

    unauth_download = client.get("/api/post-files/99999/download")
    assert unauth_download.status_code == 401
    assert_error_contract(unauth_download.get_json() or {})

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
