from __future__ import annotations

import json


def test_site_editor_state_public_default(client):
    response = client.get("/api/content/site-editor")

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    data = payload.get("data") or {}
    state = data.get("state") or {}
    assert state.get("textEdits") == {}
    assert state.get("imageEdits") == {}


def test_site_editor_mutation_requires_admin(client, create_user, login_as, csrf_headers):
    payload = {
        "textEdits": {"id:home-hero-subtext": "테스트 문구"},
        "imageEdits": {},
    }

    unauth = client.put(
        "/api/content/site-editor",
        json=payload,
        headers=csrf_headers(),
    )
    assert unauth.status_code == 401

    general = create_user(role="GENERAL", status="active")
    login_as(general)

    forbidden = client.put(
        "/api/content/site-editor",
        json=payload,
        headers=csrf_headers(),
    )
    assert forbidden.status_code == 403


def test_site_editor_save_history_and_undo_flow(
    client,
    create_user,
    login_as,
    csrf_headers,
):
    admin = create_user(role="ADMIN", status="active")
    login_as(admin)

    first_state = {
        "textEdits": {"id:home-hero-subtext": "첫 번째 문구"},
        "imageEdits": {"id:home-hero-image": "data:image/png;base64,AAA"},
    }
    second_state = {
        "textEdits": {"id:home-hero-subtext": "두 번째 문구"},
        "imageEdits": {"id:home-hero-image": "data:image/png;base64,BBB"},
    }

    save_first = client.put(
        "/api/content/site-editor",
        json=first_state,
        headers=csrf_headers(),
    )
    assert save_first.status_code == 200
    saved_first_payload = (save_first.get_json() or {}).get("data") or {}
    assert (saved_first_payload.get("state") or {}) == first_state

    save_second = client.put(
        "/api/content/site-editor",
        json=second_state,
        headers=csrf_headers(),
    )
    assert save_second.status_code == 200

    history = client.get("/api/content/site-editor/history?limit=10")
    assert history.status_code == 200
    items = ((history.get_json() or {}).get("data") or {}).get("items") or []
    assert len(items) >= 2

    undo_once = client.post(
        "/api/content/site-editor/undo",
        json={},
        headers=csrf_headers(),
    )
    assert undo_once.status_code == 200
    undo_once_state = (((undo_once.get_json() or {}).get("data") or {}).get("state") or {})
    assert undo_once_state == first_state

    undo_twice = client.post(
        "/api/content/site-editor/undo",
        json={},
        headers=csrf_headers(),
    )
    assert undo_twice.status_code == 200
    undo_twice_state = (((undo_twice.get_json() or {}).get("data") or {}).get("state") or {})
    assert undo_twice_state == {"textEdits": {}, "imageEdits": {}}

    undo_empty = client.post(
        "/api/content/site-editor/undo",
        json={},
        headers=csrf_headers(),
    )
    assert undo_empty.status_code == 404


def test_site_editor_restore_specific_history(
    client,
    create_user,
    login_as,
    csrf_headers,
):
    admin = create_user(role="ADMIN", status="active")
    login_as(admin)

    first_state = {
        "textEdits": {"id:home-hero-subtext": "히스토리 A"},
        "imageEdits": {},
    }
    second_state = {
        "textEdits": {"id:home-hero-subtext": "히스토리 B"},
        "imageEdits": {},
    }

    save_first = client.put(
        "/api/content/site-editor",
        json=first_state,
        headers=csrf_headers(),
    )
    assert save_first.status_code == 200

    save_second = client.put(
        "/api/content/site-editor",
        json=second_state,
        headers=csrf_headers(),
    )
    assert save_second.status_code == 200

    history = client.get("/api/content/site-editor/history?limit=20")
    assert history.status_code == 200
    items = ((history.get_json() or {}).get("data") or {}).get("items") or []
    assert len(items) >= 2

    target_id = None
    for item in items:
        state = item.get("state") or {}
        if (state.get("textEdits") or {}).get("id:home-hero-subtext") == "히스토리 A":
            target_id = int(item.get("id") or 0)
            break
    assert target_id and target_id > 0

    restored = client.post(
        "/api/content/site-editor/restore",
        json={"historyId": target_id},
        headers=csrf_headers(),
    )
    assert restored.status_code == 200
    restored_state = (((restored.get_json() or {}).get("data") or {}).get("state") or {})
    assert restored_state == first_state

    not_found = client.post(
        "/api/content/site-editor/restore",
        json={"historyId": 99999999},
        headers=csrf_headers(),
    )
    assert not_found.status_code == 404


def test_site_editor_update_conflict_returns_409(
    client,
    create_user,
    login_as,
    csrf_headers,
):
    admin = create_user(role="ADMIN", status="active")
    login_as(admin)

    first = client.put(
        "/api/content/site-editor",
        json={"textEdits": {"id:home-hero-subtext": "A"}, "imageEdits": {}},
        headers=csrf_headers(),
    )
    assert first.status_code == 200
    updated_at = (((first.get_json() or {}).get("data") or {}).get("updatedAt"))
    assert updated_at

    second = client.put(
        "/api/content/site-editor",
        json={"state": {"textEdits": {"id:home-hero-subtext": "B"}, "imageEdits": {}}, "ifMatchUpdatedAt": updated_at},
        headers=csrf_headers(),
    )
    assert second.status_code == 200

    stale = client.put(
        "/api/content/site-editor",
        json={"state": {"textEdits": {"id:home-hero-subtext": "C"}, "imageEdits": {}}, "ifMatchUpdatedAt": updated_at},
        headers=csrf_headers(),
    )
    assert stale.status_code == 409


def test_content_block_hero_background_range_is_normalized(
    client,
    create_user,
    login_as,
    csrf_headers,
):
    admin = create_user(role="ADMIN", status="active")
    login_as(admin)

    raw = {
        "imageOffsetX": 999,
        "imageOffsetY": -999,
        "backgroundPosX": 200,
        "backgroundPosY": -50,
    }
    response = client.put(
        "/api/content/blocks",
        json={"key": "hero_background", "contentHtml": json.dumps(raw, ensure_ascii=False)},
        headers=csrf_headers(),
    )
    assert response.status_code == 200

    listed = client.get("/api/content/blocks")
    assert listed.status_code == 200
    hero_text = ((((listed.get_json() or {}).get("data") or {}).get("items") or {}).get("hero_background") or {}).get("contentHtml") or "{}"
    parsed = json.loads(hero_text)
    assert parsed.get("imageOffsetX") == 120
    assert parsed.get("imageOffsetY") == -120
    assert parsed.get("backgroundPosX") == 100
    assert parsed.get("backgroundPosY") == 0
