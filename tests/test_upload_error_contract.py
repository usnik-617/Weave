from __future__ import annotations

import io

from contract_assertions import assert_error_contract


def test_upload_file_endpoints_keep_error_response_contract(
    client, create_user, login_as, csrf_headers
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

    general = create_user(role="GENERAL")
    login_as(general)
    forbidden_upload = client.post(
        "/api/posts/99999/files",
        data={"file": (io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "x.pdf", "application/pdf")},
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )
    assert forbidden_upload.status_code == 403
    assert_error_contract(forbidden_upload.get_json() or {})
