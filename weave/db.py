from weave import core


def get_db():
    return core.get_db_connection()


def close_db(conn):
    if conn is not None:
        conn.close()


def init_db():
    return core.init_db()
