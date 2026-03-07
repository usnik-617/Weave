from contract_assertions import assert_error_contract
from weave import post_policy
from weave import posts_routes


def _create_post(client, csrf_headers, category, title):
    response = client.post(
        "/api/posts",
        json={"category": category, "title": title, "content": f"{title}-content"},
        headers=csrf_headers(),
    )
    assert response.status_code == 201
    payload = response.get_json() or {}
    assert payload.get("success") is True
    post_id = int(((payload.get("data") or {}).get("post_id") or 0))
    assert post_id > 0
    return post_id


def test_notice_gallery_qna_create_update_delete_flow_is_preserved(
    client, create_user, login_as, csrf_headers
):
    executive = create_user(role="EXECUTIVE")
    login_as(executive)

    for category in ("notice", "gallery", "qna"):
        post_id = _create_post(client, csrf_headers, category, f"{category}-original")

        update_res = client.put(
            f"/api/posts/{post_id}",
            json={
                "category": category,
                "title": f"{category}-updated",
                "content": "updated-content",
            },
            headers=csrf_headers(),
        )
        assert update_res.status_code == 200
        update_payload = update_res.get_json() or {}
        assert update_payload.get("success") is True
        assert int(((update_payload.get("data") or {}).get("post_id") or 0)) == post_id

        detail_res = client.get(f"/api/posts/{post_id}")
        assert detail_res.status_code == 200
        detail_payload = detail_res.get_json() or {}
        detail_data = detail_payload.get("data") or {}
        assert detail_payload.get("success") is True
        assert str(detail_data.get("type") or "") == category
        assert str(detail_data.get("title") or "") == f"{category}-updated"

        delete_res = client.delete(f"/api/posts/{post_id}", headers=csrf_headers())
        assert delete_res.status_code == 200
        delete_payload = delete_res.get_json() or {}
        assert delete_payload.get("success") is True
        assert bool((delete_payload.get("data") or {}).get("deleted")) is True

        not_found_res = client.get(f"/api/posts/{post_id}")
        assert not_found_res.status_code == 404


def test_unsupported_category_returns_consistent_400_for_create_and_update(
    client, create_user, login_as, csrf_headers
):
    executive = create_user(role="EXECUTIVE")
    login_as(executive)

    create_res = client.post(
        "/api/posts",
        json={"category": "unsupported", "title": "bad-create", "content": "x"},
        headers=csrf_headers(),
    )
    assert create_res.status_code == 400
    create_payload = create_res.get_json() or {}
    assert_error_contract(create_payload)

    valid_post_id = _create_post(client, csrf_headers, "notice", "valid-notice")

    update_res = client.put(
        f"/api/posts/{valid_post_id}",
        json={"category": "unsupported", "title": "bad-update", "content": "x"},
        headers=csrf_headers(),
    )
    assert update_res.status_code == 400
    update_payload = update_res.get_json() or {}
    assert_error_contract(update_payload)


def test_category_registry_sets_are_consistent_with_policy():
    create_keys = set(posts_routes.CATEGORY_CREATE_HANDLERS.keys())
    update_keys = set(posts_routes.CATEGORY_UPDATE_HANDLERS.keys())
    delete_keys = set(posts_routes.CATEGORY_DELETE_HANDLERS.keys())

    assert create_keys == update_keys == delete_keys
    assert create_keys == {"notice", "gallery", "qna"}
    assert create_keys.issubset(set(post_policy.CREATE_ALLOWED_CATEGORIES))
