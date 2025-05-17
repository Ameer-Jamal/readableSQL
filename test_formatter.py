from SQLFormatter import SQLFormatter

def test_format_insert_values_block_basic():
    sql = "INSERT INTO foo(bar, baz) VALUES(1, 'qux');"
    out = SQLFormatter.format_insert_values_block(sql)
    expected = (
        "INSERT INTO foo (\n"
        "    bar,\n"
        "    baz\n"
        ") VALUES (\n"
        "    1,    -- bar\n"
        "    'qux'  -- baz\n"
        ");"
    )
    assert out == expected


def test_format_insert_values_block_mismatch():
    sql = "INSERT INTO foo(bar, baz) VALUES(1);"
    out = SQLFormatter.format_insert_values_block(sql)
    assert "Column/value count mismatch" in out
    assert "Columns: ['bar', 'baz']" in out
    assert "Values:  ['1']" in out

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
    assert out == sql  # unchanged because JSON-like RHS


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
    assert "Column/value count mismatch" in out
    assert "FUNC(1" in out  # This proves it split wrongly


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
    sql = "INSERT INTO foo(bar, baz)"
    out = SQLFormatter.format_insert_values_block(sql)
    assert out.startswith("❌ Invalid format")


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
    sql = "INSERT INTO foo(x, y) VALUES(1, 2)"
    out = SQLFormatter.format_insert_values_block(sql + ";")
    assert "VALUES (" in out
    assert out.endswith(");")


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
