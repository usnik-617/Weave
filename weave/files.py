def save_uploaded_file(file_storage):
    from weave import core_files

    return core_files.save_uploaded_file(file_storage)


def remove_file_safely(path):
    from weave import core_files

    return core_files.remove_file_safely(path)


def upload_url_to_path(upload_url):
    from weave import core_files

    return core_files.upload_url_to_path(upload_url)


def compute_file_sha256_from_filestorage(file_storage):
    from weave import core_files

    return core_files.compute_file_sha256_from_filestorage(file_storage)


def delete_file_if_unreferenced(conn, stored_path):
    if not stored_path:
        return
    ref = conn.execute(
        "SELECT id FROM post_files WHERE stored_path = ? LIMIT 1",
        (stored_path,),
    ).fetchone()
    if not ref:
        remove_file_safely(stored_path)


def make_thumbnail_like(url):
    if not url:
        return ""
    return url
