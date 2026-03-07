from io import BytesIO


def test_about_sections_get_schema(client):
    response = client.get("/api/about/sections")

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    data = payload.get("data") or {}
    assert isinstance(data.get("items"), dict)


def test_about_sections_update_requires_executive(
    client, create_user, login_as, csrf_headers
):
    general = create_user(role="GENERAL")
    login_as(general)

    forbidden = client.put(
        "/api/about/sections",
        json={"key": "history", "contentHtml": "text"},
        headers=csrf_headers(),
    )
    assert forbidden.status_code == 403

    executive = create_user(role="EXECUTIVE")
    login_as(executive)
    allowed = client.put(
        "/api/about/sections",
        json={"key": "history", "contentHtml": "updated"},
        headers=csrf_headers(),
    )

    assert allowed.status_code == 200
    payload = allowed.get_json() or {}
    assert payload.get("success") is True
    assert (payload.get("data") or {}).get("ok") is True


def test_about_sections_image_upload_contract(
    client, create_user, login_as, csrf_headers, png_file_bytes
):
    executive = create_user(role="EXECUTIVE")
    login_as(executive)

    response = client.post(
        "/api/about/sections/image",
        data={
            "key": "history",
            "file": (BytesIO(png_file_bytes), "about-history.png"),
        },
        headers=csrf_headers(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    payload = response.get_json() or {}
    assert payload.get("success") is True
    image_url = ((payload.get("data") or {}).get("imageUrl") or "").strip()
    assert image_url.startswith("/uploads/")


def test_content_blocks_update_and_get_schema(
    client, create_user, login_as, csrf_headers
):
    admin = create_user(role="ADMIN")
    login_as(admin)

    update_response = client.put(
        "/api/content/blocks",
        json={"key": "home_stats", "contentHtml": "<p>stats</p>"},
        headers=csrf_headers(),
    )
    assert update_response.status_code == 200
    update_payload = update_response.get_json() or {}
    assert update_payload.get("success") is True
    assert (update_payload.get("data") or {}).get("ok") is True

    get_response = client.get("/api/content/blocks")
    assert get_response.status_code == 200
    get_payload = get_response.get_json() or {}
    assert get_payload.get("success") is True
    items = (get_payload.get("data") or {}).get("items") or {}
    assert "home_stats" in items


def test_posts_list_route_still_works_after_about_split(client):
    response = client.get("/api/posts")

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    data = payload.get("data") or {}
    assert "items" in data
    assert "pagination" in data


def test_about_routes_are_registered_once_per_method(client):
    route_endpoints = {}
    target_paths = {
        "/api/about/sections",
        "/api/about/sections/image",
        "/api/content/blocks",
    }
    for rule in client.application.url_map.iter_rules():
        if rule.rule not in target_paths:
            continue
        methods = {
            method
            for method in (rule.methods or set())
            if method not in {"HEAD", "OPTIONS"}
        }
        route_endpoints.setdefault(rule.rule, set()).update(methods)

    assert route_endpoints.get("/api/about/sections") == {"GET", "PUT"}
    assert route_endpoints.get("/api/about/sections/image") == {"POST"}
    assert route_endpoints.get("/api/content/blocks") == {"GET", "PUT"}
