from __future__ import annotations

from contract_assertions import assert_error_contract, assert_success_contract


def test_admin_can_search_users_by_name_and_phone(client, create_user, login_as):
    admin = create_user(
        role="ADMIN",
        status="active",
        name="관리자",
        phone="010-9999-9999",
        username="admin_search",
    )
    target = create_user(
        role="GENERAL",
        status="pending",
        name="홍길동",
        phone="010-1234-5678",
        username="hong_user",
    )
    login_as(admin)

    response = client.get(
        "/api/admin/users/search?name=%ED%99%8D%EA%B8%B8%EB%8F%99&phone=01012345678"
    )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert_success_contract(payload)
    data = payload.get("data") or {}
    assert int(data.get("total") or 0) == 1
    item = (data.get("items") or [None])[0]
    assert item["id"] == int(target["id"])
    assert item["name"] == "홍길동"
    assert item["phone"] == "010-1234-5678"


def test_non_admin_cannot_search_users_by_identity(client, create_user, login_as):
    member = create_user(role="MEMBER", status="active", username="member_search")
    login_as(member)

    response = client.get(
        "/api/admin/users/search?name=%ED%99%8D%EA%B8%B8%EB%8F%99&phone=01012345678"
    )

    assert response.status_code == 403
    assert_error_contract(response.get_json() or {})


def test_admin_can_change_user_role_by_identity_flow(
    client, create_user, login_as, csrf_headers
):
    admin = create_user(
        role="ADMIN",
        status="active",
        name="관리자",
        phone="010-9999-9999",
        username="admin_ops",
    )
    target = create_user(
        role="GENERAL",
        status="pending",
        name="홍길동",
        phone="010-1234-5678",
        username="hong_role",
    )
    login_as(admin)

    response = client.patch(
        f"/api/admin/users/{target['id']}/role",
        json={"role": "MEMBER"},
        headers=csrf_headers(),
    )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert_success_contract(payload)
    data = payload.get("data") or {}
    assert data.get("user", {}).get("role") == "MEMBER"
    assert data.get("user", {}).get("status") == "active"


def test_admin_role_change_immediately_updates_post_permissions(
    client, create_user, login_as, csrf_headers
):
    admin = create_user(
        role="ADMIN",
        status="active",
        name="관리자",
        phone="010-9999-1111",
        username="admin_ops_2",
    )
    target = create_user(
        role="GENERAL",
        status="active",
        name="권한테스트",
        phone="010-3333-4444",
        username="target_general_2",
    )

    login_as(admin)
    promote = client.patch(
        f"/api/admin/users/{target['id']}/role",
        json={"role": "EXECUTIVE"},
        headers=csrf_headers(),
    )
    assert promote.status_code == 200

    login_as(target)
    notice_create = client.post(
        "/api/posts",
        json={"category": "notice", "title": "권한 변경 공지", "content": "본문"},
        headers=csrf_headers(),
    )
    assert notice_create.status_code in (200, 201)


def test_admin_role_demotion_immediately_updates_comment_permissions(
    client, create_user, create_post_record, login_as, csrf_headers
):
    admin = create_user(
        role="ADMIN",
        status="active",
        name="관리자",
        phone="010-9999-2222",
        username="admin_ops_3",
    )
    target = create_user(
        role="MEMBER",
        status="active",
        name="댓글권한테스트",
        phone="010-4444-5555",
        username="target_member_3",
    )
    notice_id = create_post_record(category="notice", author_id=admin["id"])

    login_as(admin)
    demote = client.patch(
        f"/api/admin/users/{target['id']}/role",
        json={"role": "GENERAL"},
        headers=csrf_headers(),
    )
    assert demote.status_code == 200

    login_as(target)
    comment = client.post(
        f"/api/posts/{notice_id}/comments",
        json={"content": "일반으로 강등 후 댓글 시도"},
        headers=csrf_headers(),
    )
    assert comment.status_code == 403


def test_executive_can_search_and_change_general_member_users(
    client, create_user, login_as, csrf_headers
):
    executive = create_user(
        role="EXECUTIVE",
        status="active",
        name="운영진",
        phone="010-5555-1111",
        username="executive_ops",
    )
    target = create_user(
        role="GENERAL",
        status="active",
        name="홍길동",
        phone="010-1234-5678",
        username="hong_exec_target",
    )
    login_as(executive)

    search = client.get(
        "/api/admin/users/search?name=%ED%99%8D%EA%B8%B8%EB%8F%99&phone=010-1234-5678"
    )
    assert search.status_code == 200
    search_payload = search.get_json() or {}
    assert_success_contract(search_payload)
    assert int((search_payload.get("data") or {}).get("total") or 0) == 1

    promote = client.patch(
        f"/api/admin/users/{target['id']}/role",
        json={"role": "MEMBER"},
        headers=csrf_headers(),
    )
    assert promote.status_code == 200
    promote_payload = promote.get_json() or {}
    assert_success_contract(promote_payload)
    assert (promote_payload.get("data") or {}).get("user", {}).get("role") == "MEMBER"


def test_executive_cannot_change_other_executive_or_admin(
    client, create_user, login_as, csrf_headers
):
    executive = create_user(
        role="EXECUTIVE",
        status="active",
        name="운영진",
        phone="010-5555-2222",
        username="executive_ops_2",
    )
    peer = create_user(
        role="EXECUTIVE",
        status="active",
        name="다른운영진",
        phone="010-5555-3333",
        username="executive_peer",
    )
    admin = create_user(
        role="ADMIN",
        status="active",
        name="관리자",
        phone="010-5555-4444",
        username="executive_admin_peer",
    )
    login_as(executive)

    peer_change = client.patch(
        f"/api/admin/users/{peer['id']}/role",
        json={"role": "MEMBER"},
        headers=csrf_headers(),
    )
    admin_change = client.patch(
        f"/api/admin/users/{admin['id']}/role",
        json={"role": "MEMBER"},
        headers=csrf_headers(),
    )

    assert peer_change.status_code == 403
    assert admin_change.status_code == 400
    assert_error_contract(peer_change.get_json() or {})
    assert_error_contract(admin_change.get_json() or {})


def test_admin_cannot_change_admin_or_self_role(
    client, create_user, login_as, csrf_headers
):
    admin = create_user(
        role="ADMIN",
        status="active",
        name="관리자",
        phone="010-9999-3333",
        username="admin_self",
    )
    other_admin = create_user(
        role="ADMIN",
        status="active",
        name="서브관리자",
        phone="010-8888-8888",
        username="admin_other",
    )
    login_as(admin)

    self_response = client.patch(
        f"/api/admin/users/{admin['id']}/role",
        json={"role": "MEMBER"},
        headers=csrf_headers(),
    )
    other_response = client.patch(
        f"/api/admin/users/{other_admin['id']}/role",
        json={"role": "MEMBER"},
        headers=csrf_headers(),
    )

    assert self_response.status_code == 400
    assert other_response.status_code == 400
    assert_error_contract(self_response.get_json() or {})
    assert_error_contract(other_response.get_json() or {})
