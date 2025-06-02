from SQLFormatter import SQLFormatter

def test_format_insert_values_block_basic():
    sql = "INSERT INTO foo(bar, baz) VALUES(1, 'qux');"
    out = SQLFormatter.format_insert_values_block(sql)
    expected = (
        "INSERT INTO foo (\n"
        "    bar,\n"
        "    baz\n"
        ") VALUES\n"  # Changed
        "    (\n"      # Changed
        "        1,    -- bar\n"  
        "        'qux'  -- baz\n" 
        "    );"
    )
    assert out.strip() == expected.strip()


def test_format_insert_values_block_mismatch():
    sql = "INSERT INTO foo(bar, baz) VALUES(1);"
    out = SQLFormatter.format_insert_values_block(sql)
    # Check for key parts of the new user-friendly error message
    assert "❌ Mismatch in row 1 for table 'foo'" in out
    assert "Expected 2 values for columns: bar, baz" in out
    assert "But found 1 values: 1" in out

def test_format_insert_select_block_basic():
    sql = "INSERT INTO foo(col1, col2) SELECT a, b FROM bar;"
    out = SQLFormatter.format_insert_select_block(sql)
    expected = (
        "INSERT INTO foo (\n"
        "    col1,\n"
        "    col2\n"
        ") SELECT\n"
        "    a,  -- col1\n"
        "    b   -- col2\n"
        "FROM bar;"
    )
    assert out == expected


def test_extract_insert_statements():
    sql = """
    INSERT INTO t1(a) VALUES(1);
    INSERT INTO t2(x, y) SELECT x, y FROM other;
    """
    stmts = SQLFormatter.extract_insert_statements(sql)
    assert any("VALUES(1);" in s for s in stmts)
    assert any("SELECT x, y FROM other;" in s for s in stmts)
    assert len(stmts) == 2


def test_format_set_block_pure():
    sql = "SET @A = 1;\nSET @BB := 2;"
    out = SQLFormatter.format_set_block(sql)
    expected = "SET @A  = 1;\nSET @BB := 2;"
    assert out == expected


def test_format_set_block_skip_json():
    sql = "SET @J = {'a':1};"
    out = SQLFormatter.format_set_block(sql)
    assert out == sql


def test_format_update_block_basic():
    sql = "UPDATE foo\nSET a = 1, b = 2\nWHERE id = 3;"
    out = SQLFormatter.format_update_block(sql)
    lines = out.splitlines()
    assert lines[0] == "UPDATE foo"
    assert lines[1] == "  SET"
    assert "a = 1," in lines[2]
    assert "b = 2" in lines[3]
    assert lines[4].startswith("WHERE id = 3")


def test_format_all_update_pretty_json_toggle():
    sql = "UPDATE foo\nSET json = '{\"x\":1, \"y\":2}'\nWHERE id = 1;"
    pretty = SQLFormatter.format_all(sql, pretty_json=True)
    assert "{\n    \"x\": 1," in pretty
    no_pretty = SQLFormatter.format_all(sql, pretty_json=False)
    # raw JSON remains inline
    assert "'{\"x\":1, \"y\":2}'" in no_pretty


def test_format_create_table_basic():
    sql = "CREATE TABLE t (a int,b varchar(10));"
    out = SQLFormatter.format_create_table(sql)
    assert "CREATE TABLE t" in out
    assert "a int" in out
    assert "b varchar(10)" in out


def test_format_alter_table():
    sql = "ALTER TABLE   foo  ADD COLUMN   bar int  ;"
    out = SQLFormatter.format_alter_table(sql)
    # whitespace collapsed
    assert out == "ALTER TABLE foo ADD COLUMN bar int ;"


def test_format_all_mixed():
    sql = (
        "INSERT INTO foo(bar) VALUES(1);\n"
        "SET @X=2;\n"
        "UPDATE foo SET bar=3 WHERE id=1;\n"
        "ALTER TABLE foo ADD col int;\n"
    )
    out = SQLFormatter.format_all(sql)
    assert "INSERT INTO foo" in out
    assert "SET @X" in out
    assert "UPDATE foo" in out
    assert "ALTER TABLE foo ADD col int" in out

def test_insert_with_nested_functions():
    sql = "INSERT INTO foo(a, b) VALUES(FUNC(1, 2), 'text');"
    out = SQLFormatter.format_insert_values_block(sql)
    expected = (
        "INSERT INTO foo (\n"
        "    a,\n"
        "    b\n"
        ") VALUES\n"  
        "    (\n"      
        "        FUNC(1, 2), -- a\n"  # Indentation
        "        'text'       -- b\n"  # Indentation
        "    );"
    )
    assert out.strip() == expected.strip()

def test_insert_with_comma_in_string():
    sql = "INSERT INTO foo(name, note) VALUES('Doe, John', 'Checked');"
    out = SQLFormatter.format_insert_values_block(sql)
    assert "'Doe, John'" in out


def test_insert_with_quoted_identifiers():
    sql = 'INSERT INTO "user"("select", "from") VALUES(1, 2);'
    out = SQLFormatter.format_insert_values_block(sql)
    assert '"select"' in out
    assert '-- "select"' in out

def test_format_all_with_comments_and_blank_lines():
    sql = """
-- Add a new user
INSERT INTO users(id, name) VALUES(1, 'Alice');

-- Update the record
UPDATE users
SET name = 'Alice B'
WHERE id = 1;

-- Just a comment
"""
    out = SQLFormatter.format_all(sql)
    assert "-- Add a new user" in out
    assert "INSERT INTO users" in out
    assert "UPDATE users" in out
    assert "WHERE id = 1;" in out


def test_format_all_with_unrecognized_block():
    sql = "DROP TABLE IF EXISTS foo;"
    out = SQLFormatter.format_all(sql)
    assert "DROP TABLE IF EXISTS foo;" in out


def test_malformed_insert_missing_values():
    sql = "INSERT INTO foo(bar, baz)"  # Missing VALUES clause
    # format_insert_values_block expects a semicolon at the end of the statement string for its regex.
    out = SQLFormatter.format_insert_values_block(sql + ";")
    assert out.startswith("❌ Invalid INSERT statement structure. Could not identify table, columns, or VALUES clause.")

def test_embedded_json_toggle():
    sql = """UPDATE config SET data = '{"a":1,"b":[2,3]}';"""
    out_pretty = SQLFormatter.format_all(sql, pretty_json=True)
    out_raw = SQLFormatter.format_all(sql, pretty_json=False)
    assert '\n    "a": 1,' in out_pretty
    assert '{"a":1,"b":[2,3]}' in out_raw


def test_insert_select_with_reserved_word():
    sql = "INSERT INTO results(id, `select`) SELECT 1, val FROM dummy;"
    out = SQLFormatter.format_insert_select_block(sql)
    assert "SELECT" in out
    assert "FROM dummy;" in out


def test_update_block_multi_line_set():
    sql = """UPDATE bar
SET a = 1,
b = '{"c":2,"d":3}'
WHERE id = 4;"""
    out = SQLFormatter.format_update_block(sql)
    assert "SET" in out
    assert "a = 1" in out
    assert 'b = \'{"c":2,"d":3}\'' in out or 'b = "{' in out


def test_insert_with_no_semicolon():
    sql = "INSERT INTO foo(x, y) VALUES(1, 2)" # No semicolon
    # format_insert_values_block expects a semicolon from the way format_all splits
    out = SQLFormatter.format_insert_values_block(sql + ";")
    assert ") VALUES\n" in out # Check for VALUES on its line
    assert "\n    (" in out     # Check for ( on the next indented line
    assert out.strip().endswith(");")


def test_extract_insert_statements_with_mixed_input():
    sql = """
INSERT INTO foo(a, b) VALUES(1, 2);
-- comment
INSERT INTO bar(x, y) SELECT id, val FROM dummy;
UPDATE config SET z = 1;
"""
    statements = SQLFormatter.extract_insert_statements(sql)
    assert len(statements) == 2
    assert "VALUES" in statements[0]
    assert "SELECT" in statements[1]

def test_format_delete_block_basic():
    sql = "DELETE FROM users WHERE is_deleted = 1 AND last_login < '2023-01-01';"
    out = SQLFormatter.format_delete_block(sql)
    lines = out.splitlines()
    assert lines[0] == "DELETE FROM users"
    assert lines[1] == "WHERE"
    assert any("is_deleted = 1" in line for line in lines)
    assert any("last_login < '2023-01-01'" in line for line in lines)
    assert out.endswith(";")

def test_format_delete_block_no_where():
    sql = "DELETE FROM logs;"
    out = SQLFormatter.format_delete_block(sql)
    assert out == "DELETE FROM logs;"

def test_format_drop_table():
    sql = "DROP TABLE IF EXISTS temp_users;"
    out = SQLFormatter.format_simple_single_line(sql)
    assert out == "DROP TABLE IF EXISTS temp_users;"

def test_format_drop_index():
    sql = "DROP INDEX IF EXISTS idx_temp;"
    out = SQLFormatter.format_simple_single_line(sql)
    assert out == "DROP INDEX IF EXISTS idx_temp;"

def test_format_case_expression_basic():
    sql = "SELECT CASE WHEN a = 1 THEN 'one' WHEN a = 2 THEN 'two' ELSE 'other' END AS val FROM tbl;"
    out = SQLFormatter.format_all(sql)

    expected = (
        "SELECT CASE\n"
        "    WHEN a = 1 THEN 'one'\n"
        "    WHEN a = 2 THEN 'two'\n"
        "    ELSE 'other'\n"
        "END AS val FROM tbl;"
    )

    assert out.strip() == expected.strip()

def test_format_delete_block_with_and_preserved():
    sql = "DELETE FROM users WHERE is_active = FALSE AND created_at < '2023-01-01';"
    out = SQLFormatter.format_delete_block(sql)
    lines = out.splitlines()

    # First line must be "DELETE FROM users"
    assert lines[0] == "DELETE FROM users"

    # Second line must be "WHERE"
    assert lines[1] == "WHERE"

    # Third line: first condition, no "AND" prefix
    assert lines[2].strip() == "is_active = FALSE"

    # Fourth line: must begin with "AND "
    assert lines[3].startswith("    AND ")
    assert "created_at < '2023-01-01'" in lines[3]

    # Ensure final output ends with a semicolon
    assert out.strip().endswith(";")
def test_format_create_table_multiple_columns():
    sql = 'CREATE TABLE t(a INT, b VARCHAR(10), c JSON);'
    out = SQLFormatter.format_create_table(sql)
    lines = out.splitlines()
    # First line should be "CREATE TABLE t ("
    assert lines[0] == "CREATE TABLE t ("
    # There should be exactly three column lines (with commas on the first two)
    assert lines[1].strip() == "a INT,"
    assert lines[2].strip() == "b VARCHAR(10),"
    assert lines[3].strip() == "c JSON"
    # Last line should be ");"
    assert lines[4] == ");"

def test_format_alter_table_multiple_actions():
    sql = "ALTER TABLE foo ADD COLUMN x INT, DROP COLUMN y, RENAME TO foo2;"
    out = SQLFormatter.format_alter_table(sql)
    lines = out.splitlines()
    # First line is the header
    assert lines[0] == "ALTER TABLE foo"
    # Next lines should be indented and end with commas except the last
    assert lines[1].strip() == "ADD COLUMN x INT,"
    assert lines[2].strip() == "DROP COLUMN y,"
    assert lines[3].strip() == "RENAME TO foo2"
    # Final line is just a semicolon
    assert lines[4] == ";"

def test_format_update_block_multiple_assignments():
    sql = "UPDATE tbl SET a = 1, b = 2, c = 3 WHERE id = 99;"
    out = SQLFormatter.format_update_block(sql)
    lines = out.splitlines()
    # First line
    assert lines[0] == "UPDATE tbl"
    # Exactly two spaces before SET
    assert lines[1] == "  SET"
    # Three assignment lines (each with comma except the last)
    assert lines[2].strip() == "a = 1,"
    assert lines[3].strip() == "b = 2,"
    assert lines[4].strip() == "c = 3"
    # WHERE clause on its own line
    assert lines[5] == "WHERE id = 99;"

def test_format_drop_table_whitespace_collapsed():
    sql = "DROP TABLE    IF EXISTS   test_table   ;"
    out = SQLFormatter.format_simple_single_line(sql)
    # Exactly one space between each token, and a single semicolon
    assert out == "DROP TABLE IF EXISTS test_table ;"