from weave import core_db


def test_convert_qmark_to_pyformat_basic():
    sql = "SELECT * FROM users WHERE id = ? AND status = ?"
    out = core_db._convert_qmark_to_pyformat(sql)
    assert out.count("%s") == 2


def test_convert_qmark_preserves_literal_question_mark():
    sql = "SELECT '?' AS marker, id FROM users WHERE name = ?"
    out = core_db._convert_qmark_to_pyformat(sql)
    assert "'?'" in out
    assert out.endswith("name = %s")


def test_convert_sqlite_date_functions():
    sql = "SELECT date('now'), date('now', '+7 day'), datetime('now')"
    out = core_db._convert_qmark_to_pyformat(sql)
    assert "CURRENT_DATE" in out
    assert "CURRENT_TIMESTAMP" in out
