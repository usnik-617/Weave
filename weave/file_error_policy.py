from __future__ import annotations

from weave import error_messages
from weave.responses import error_response


def unauthorized():
    return error_response(error_messages.UNAUTHORIZED, 401)


def member_required_upload():
    return error_response(error_messages.FILE_MEMBER_REQUIRED_UPLOAD, 403)


def member_required_access():
    return error_response(error_messages.FILE_MEMBER_REQUIRED_ACCESS, 403)


def post_not_found():
    return error_response(error_messages.FILE_POST_NOT_FOUND, 404)


def invalid_path():
    return error_response(error_messages.FILE_INVALID_PATH, 400)


def file_not_found():
    return error_response(error_messages.FILE_NOT_FOUND, 404)


def stored_file_missing():
    return error_response(error_messages.FILE_STORED_MISSING, 404)


def expires_at_invalid():
    return error_response(error_messages.FILE_EXPIRES_INVALID, 400)


def upload_processing_failed():
    return error_response(error_messages.FILE_UPLOAD_PROCESS_FAILED, 400)


def gallery_thumb_failed(status=500):
    return error_response(error_messages.FILE_GALLERY_THUMB_FAILED, status)
