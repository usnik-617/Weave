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
