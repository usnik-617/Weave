from __future__ import annotations

import io


def test_gallery_create_persists_activity_dates(client, create_user, login_as, csrf_headers):
    staff = create_user(role='EXECUTIVE')
    login_as(staff)

    response = client.post(
        '/api/posts',
        json={
            'category': 'gallery',
            'title': '봄 봉사 사진',
            'content': '<p>본문</p>',
            'activityStartDate': '2026-04-10',
            'activityEndDate': '2026-04-11',
        },
        headers=csrf_headers(),
    )

    assert response.status_code == 201
    post_id = int((((response.get_json() or {}).get('data') or {}).get('post_id') or 0))
    assert post_id > 0

    detail = client.get(f'/api/posts/{post_id}')
    payload = (detail.get_json() or {}).get('data') or {}
    assert payload.get('volunteerStartDate') == '2026-04-10'
    assert payload.get('volunteerEndDate') == '2026-04-11'


def test_gallery_update_persists_activity_dates(client, create_user, login_as, csrf_headers, create_post_record):
    staff = create_user(role='EXECUTIVE')
    login_as(staff)
    post_id = create_post_record(category='gallery', author_id=staff['id'])

    response = client.put(
        f'/api/posts/{post_id}',
        json={
            'category': 'gallery',
            'title': '수정된 갤러리',
            'content': '<p>수정</p>',
            'activityStartDate': '2026-05-01',
            'activityEndDate': '2026-05-03',
        },
        headers=csrf_headers(),
    )

    assert response.status_code == 200
    detail = client.get(f'/api/posts/{post_id}')
    payload = (detail.get_json() or {}).get('data') or {}
    assert payload.get('volunteerStartDate') == '2026-05-01'
    assert payload.get('volunteerEndDate') == '2026-05-03'


def test_notice_batch_upload_accepts_multiple_images(client, create_user, login_as, csrf_headers, create_post_record, png_file_bytes):
    staff = create_user(role='EXECUTIVE')
    login_as(staff)
    post_id = create_post_record(category='notice', author_id=staff['id'])

    response = client.post(
        f'/api/posts/{post_id}/files/batch',
        data={
            'files': [
                (io.BytesIO(png_file_bytes), 'one.png', 'image/png'),
                (io.BytesIO(png_file_bytes), 'two.png', 'image/png'),
                (io.BytesIO(png_file_bytes), 'three.png', 'image/png'),
            ],
            'tokens': ['a', 'b', 'c'],
        },
        headers=csrf_headers(),
        content_type='multipart/form-data',
    )

    assert response.status_code == 201
    payload = (response.get_json() or {}).get('data') or {}
    assert int(payload.get('count') or 0) == 3
    assert int(payload.get('failed_count') or 0) == 0
