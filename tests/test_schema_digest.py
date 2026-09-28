# tests/test_schema_digest.py
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import schema_digest


class TestSchemaDigest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="schema_digest_test_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_sqlite_file_lists_tables_and_columns(self):
        db_path = os.path.join(self.root, "app.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER)")
        conn.commit()
        conn.close()

        result = schema_digest.digest(db_path)
        self.assertIn("2 tables", result)
        self.assertIn("users(id INTEGER, name TEXT)", result)
        self.assertIn("orders(id INTEGER, user_id INTEGER)", result)

    def test_sql_file_parses_create_table(self):
        sql_path = os.path.join(self.root, "migration.sql")
        with open(sql_path, "w") as fh:
            fh.write(
                "CREATE TABLE users (\n  id INT,\n  name VARCHAR\n);\n"
            )
        result = schema_digest.digest(sql_path)
        self.assertIn("1 tables", result)
        self.assertIn("users(id, name)", result)

    def test_unsupported_extension(self):
        path = os.path.join(self.root, "notes.txt")
        with open(path, "w") as fh:
            fh.write("nothing here")
        result = schema_digest.digest(path)
        self.assertIn("unsupported extension", result)


if __name__ == "__main__":
    unittest.main()
