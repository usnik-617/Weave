from __future__ import annotations

from weave.ops_requirements import validate_runtime_separation


def test_development_mode_warns_for_local_stack(monkeypatch):
    monkeypatch.setenv('WEAVE_ENV', 'development')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///weave.db')
    monkeypatch.setenv('WEAVE_STORAGE_BACKEND', 'local')
    monkeypatch.setenv('WEAVE_MEDIA_QUEUE_BACKEND', 'inline')

    report = validate_runtime_separation()

    assert report['env'] == 'development'
    assert report['db_mode'] == 'sqlite'
    assert report['storage_backend'] == 'local'
    assert report['issues'] == []
    assert len(report['warnings']) >= 2


def test_production_mode_requires_external_services(monkeypatch):
    monkeypatch.setenv('WEAVE_ENV', 'production')
    monkeypatch.setenv('WEAVE_REQUIRE_EXTERNAL_SERVICES', '1')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///weave.db')
    monkeypatch.setenv('WEAVE_STORAGE_BACKEND', 'local')
    monkeypatch.setenv('WEAVE_MEDIA_QUEUE_BACKEND', 'inline')
    monkeypatch.delenv('WEAVE_REDIS_URL', raising=False)

    report = validate_runtime_separation()

    assert report['strict'] is True
    assert report['db_mode'] == 'sqlite'
    assert report['storage_backend'] == 'local'
    assert len(report['issues']) >= 3


def test_production_mode_r2_rq_postgres_has_no_issues(monkeypatch):
    monkeypatch.setenv('WEAVE_ENV', 'production')
    monkeypatch.setenv('WEAVE_REQUIRE_EXTERNAL_SERVICES', '1')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://weave:pw@localhost:5432/weave')
    monkeypatch.setenv('WEAVE_STORAGE_BACKEND', 'r2')
    monkeypatch.setenv('WEAVE_MEDIA_QUEUE_BACKEND', 'rq')
    monkeypatch.setenv('WEAVE_REDIS_URL', 'redis://127.0.0.1:6379/0')
    monkeypatch.setenv('WEAVE_S3_BUCKET', 'weave-prod')
    monkeypatch.setenv('WEAVE_S3_ENDPOINT_URL', 'https://example.r2.cloudflarestorage.com')
    monkeypatch.setenv('WEAVE_CDN_BASE_URL', 'https://cdn.example.com')

    report = validate_runtime_separation()

    assert report['db_mode'] == 'postgres'
    assert report['storage_backend'] == 'r2'
    assert report['queue_backend'] == 'rq'
    assert report['issues'] == []
