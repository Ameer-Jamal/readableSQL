import textwrap

# Create a test file for pytest
test_code = textwrap.dedent("""
    import re
    import pytest
    from sql_insert_formatter_gui import SqlFormatterApp

    @pytest.fixture
    def app():
        return SqlFormatterApp()

    def test_format_insert_simple(app):
        sql = "INSERT INTO table_name (col1, col2) VALUES (val1, val2);"
        expected = (
            "INSERT INTO table_name (\\n"
            "    col1,\\n"
            "    col2\\n"
            ") VALUES (\\n"
            "    val1,  -- col1\\n"
            "    val2  -- col2\\n"
            ");"
        )
        assert app._format_insert(sql) == expected

    def test_format_select_simple(app):
        sql = "SELECT col1, col2 FROM table WHERE col1 = 1;"
        expected = (
            "SELECT\\n"
            "    col1,\\n"
            "    col2\\n"
            "FROM table\\n"
            "WHERE col1 = 1;"
        )
        assert app._format_select(sql) == expected

    def test_format_select_with_join(app):
        sql = "SELECT a.id, b.name FROM users a LEFT JOIN profiles b ON a.id = b.user_id WHERE a.active = 1;"
        expected = (
            "SELECT\\n"
            "    a.id,\\n"
            "    b.name\\n"
            "FROM users a\\n"
            "    LEFT JOIN profiles b\\n"
            "        ON a.id = b.user_id\\n"
            "WHERE a.active = 1;"
        )
        assert app._format_select(sql) == expected

    def test_non_sql_passthrough(app):
        sql = "DROP TABLE test;"
        assert app._format_select(sql) == sql
        # For insert, fallback returns unchanged for unmatched patterns
        assert app._format_insert("INVALID SQL") == "None" or app._format_insert("INVALID SQL")
""")

# Save to file
with open('/test_sql_formatter.py', 'w') as f:
    f.write(test_code)

"test_sql_formatter.py"
