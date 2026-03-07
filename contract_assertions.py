from __future__ import annotations


def assert_paginated_items_contract(data):
    assert isinstance(data, dict)
    assert "items" in data
    assert "pagination" in data

    pagination = data.get("pagination") or {}
    for key in ("total", "page", "pageSize", "totalPages"):
        assert key in pagination


def assert_item_has_keys(item, required_keys):
    assert isinstance(item, dict)
    for key in required_keys:
        assert key in item


def assert_error_contract(payload):
    assert isinstance(payload, dict)
    assert payload.get("success") is False
    assert isinstance(payload.get("error"), str)
    assert payload.get("error")


def assert_success_contract(payload):
    assert isinstance(payload, dict)
    assert payload.get("success") is True
    assert "data" in payload


def assert_user_contract(user_payload):
    assert isinstance(user_payload, dict)
    for key in (
        "id",
        "username",
        "nickname",
        "role",
        "status",
    ):
        assert key in user_payload
