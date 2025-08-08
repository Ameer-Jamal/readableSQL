import json
import re
from typing import List


class SQLFormatter:
    """
    The main class containing the logic for formatting the SQL statements.
    """

    # Class-level regex patterns
    INSERT_SELECT_PATTERN = re.compile(
        r"INSERT\s+INTO\s+[^\s(]+\s*\(.*?\)\s*SELECT\b",
        re.IGNORECASE | re.DOTALL,
    )
    INSERT_INTO_PATTERN = re.compile(r"^INSERT\s+INTO", re.IGNORECASE)
    SET_PATTERN = re.compile(r"^SET\s+[@\w]+\s*[:=]", re.IGNORECASE)
    CREATE_TABLE_PATTERN = re.compile(r"^CREATE TABLE", re.IGNORECASE)
    ALTER_TABLE_PATTERN = re.compile(r"^ALTER TABLE", re.IGNORECASE)
    UPDATE_PATTERN = re.compile(r"^UPDATE", re.IGNORECASE)
    DELETE_FROM_PATTERN = re.compile(r"^DELETE FROM", re.IGNORECASE)
    DROP_PATTERN = re.compile(r"^(DROP TABLE|DROP INDEX)", re.IGNORECASE)

    # Indentation constants
    INDENT_1 = "    "
    INDENT_2 = "  "

    # Mapping of patterns to formatting methods
    _DISPATCH_MAP = [
        (INSERT_SELECT_PATTERN, "format_insert_select_block"),
        (INSERT_INTO_PATTERN, "format_insert_values_block"),
        (SET_PATTERN, "format_set_block"),
        (CREATE_TABLE_PATTERN, "format_create_table"),
        (ALTER_TABLE_PATTERN, "format_alter_table"),
        (UPDATE_PATTERN, "format_update_block"),
        (DELETE_FROM_PATTERN, "format_delete_block"),
        (DROP_PATTERN, "format_simple_single_line"),
    ]

    @staticmethod
    def _collapse_whitespace(text: str) -> str:
        """Collapse all repeated whitespace characters into a single space."""
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _trim_semicolon(text: str) -> str:
        """Strip trailing whitespace and any semicolons at the end."""
        return text.strip().rstrip(";")

    @staticmethod
    def format_all(sql: str, pretty_json: bool = True) -> str:
        """
        Break a multi-statement SQL string into separate blocks, format each block
        according to its type, and return the concatenated result.

        :param sql: The raw SQL input containing one or more statements.
        :param pretty_json: Whether to pretty-print embedded JSON within UPDATE statements.
        :return: A formatted SQL string with blocks separated by blank lines.
        """
        sql = sql.strip()
        parts = re.split(r";\s*\n", sql, flags=re.DOTALL)
        if not parts or (len(parts) == 1 and not parts[0].strip()):
            return ""
        formatted_blocks = []

        for part_content in parts:
            part_content = part_content.strip()
            if not part_content:
                continue

            cleaned = re.sub(r"^(?:\s*(?:/\*.*?\*/|--[^\n]*))*", "", part_content,
                             flags=re.DOTALL)

            upper_part = cleaned.upper()

            # Dispatch based on the first matching pattern
            handler_name = None
            for pattern, method_name in SQLFormatter._DISPATCH_MAP:
                subject = cleaned if pattern is SQLFormatter.INSERT_SELECT_PATTERN else upper_part
                if pattern.search(subject):
                    handler_name = method_name
                    break

            if handler_name:
                method = getattr(SQLFormatter, handler_name)
                formatted_part = method(part_content + ";")
                if handler_name == "format_update_block" and pretty_json:
                    formatted_part = SQLFormatter._format_embedded_json(formatted_part)
            else:
                formatted_part = part_content if part_content.endswith(";") else part_content + ";"

            formatted_part = SQLFormatter.format_case_expression(formatted_part)
            formatted_part = re.sub(r";{2,}$", ";", formatted_part)
            formatted_blocks.append(formatted_part)

        return "\n\n".join(formatted_blocks)

    @staticmethod
    def format_insert_values_block(sql: str) -> str:
        """
        Format an INSERT INTO ... VALUES(...) statement with aligned columns, each
        row on its own lines, and inline comments indicating column names.

        :param sql: The full INSERT statement ending with a semicolon.
        :return: A pretty-printed INSERT statement or an error string on mismatch.
        """
        table_m = re.search(r"INSERT\s+INTO\s+([^\s(]+)", sql, re.IGNORECASE)
        cols_m = re.search(
            r"INSERT\s+INTO\s+[^\s(]+\s*\((.*?)\)\s*VALUES",
            sql,
            re.DOTALL | re.IGNORECASE
        )
        if not cols_m:
            return "❌ Invalid INSERT statement structure (columns not found)."

        values_block_m = re.search(
            r"\)\s*VALUES\s*([\s\S]+?);",  # note the leading \)
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not values_block_m:
            return "❌ VALUES clause not found."

        if not table_m or not cols_m or not values_block_m:
            return "❌ Invalid INSERT statement structure. Could not identify table, columns, or VALUES clause."

        table_name = table_m.group(1)
        cols_str = cols_m.group(1)
        cols = [c.strip() for c in cols_str.split(",")]

        values_content_raw = values_block_m.group(1).strip()
        values_content_raw = re.sub(r"/\*.*?\*/", "", values_content_raw, flags=re.DOTALL)

        individual_row_strings_content = []

        temp_delimiter = "<ROW_DELIMITER_TEMP_VALS>"
        processed_for_split = re.sub(r"\)\s*,\s*\(", f"){temp_delimiter}(", values_content_raw)

        if temp_delimiter in processed_for_split:
            row_parts_with_parens = processed_for_split.split(temp_delimiter)
        else:
            row_parts_with_parens = [values_content_raw]

        for row_part_with_parens in row_parts_with_parens:
            row_part_stripped = row_part_with_parens.strip()
            if row_part_stripped.startswith("(") and row_part_stripped.endswith(")"):
                individual_row_strings_content.append(row_part_stripped[1:-1].strip())
            elif not row_part_stripped:
                continue
            else:
                return (
                    "❌ Error parsing rows in VALUES. Ensure rows are correctly parenthesized "
                    "and separated by commas (e.g., VALUES (r1v1, r1v2), (r2v1, r2v2))."
                )

        if not individual_row_strings_content:
            if values_content_raw == "()":
                if not cols:
                    return f"INSERT INTO {table_name}\nVALUES ();"
                else:
                    return (
                        f"❌ Mismatch for table '{table_name}': {len(cols)} columns "
                        f"({', '.join(cols)}) defined, but VALUES clause is empty '()'."
                    )
            return f"❌ No value rows found in VALUES clause for table '{table_name}'."

        indent = SQLFormatter.INDENT_1
        output_lines = [f"INSERT INTO {table_name} ("]
        for i, col in enumerate(cols):
            comma = "," if i < len(cols) - 1 else ""
            output_lines.append(f"{indent}{col}{comma}")

        output_lines.append(") VALUES")

        for row_idx, row_values_str_content in enumerate(individual_row_strings_content):
            normalized_row_values_str = re.sub(r"\s*\n\s*", " ", row_values_str_content.strip())
            vals_for_this_row = SQLFormatter.smart_split_csv(normalized_row_values_str)

            if not vals_for_this_row and not cols:
                if row_idx == 0:
                    output_lines.append(f"{indent}(")
                else:
                    output_lines.append(f"{indent},(")
                output_lines.append(f"{indent})")
                continue
            elif not vals_for_this_row and cols:
                return (
                    f"❌ Mismatch in row {row_idx + 1} for table '{table_name}': "
                    f"Values are empty, but {len(cols)} columns are defined: {', '.join(cols)}."
                )

            if len(cols) != len(vals_for_this_row):
                return (
                    f"❌ Mismatch in row {row_idx + 1} for table '{table_name}':\n"
                    f"    Expected {len(cols)} values for columns: {', '.join(cols)}\n"
                    f"    But found {len(vals_for_this_row)} values: {', '.join(vals_for_this_row)}"
                )

            if row_idx == 0:
                output_lines.append(f"{indent}(")
            else:
                output_lines.append(f"{indent},(")

            val_comma_for_this_row = [
                vals_for_this_row[i] + ("," if i < len(vals_for_this_row) - 1 else "")
                for i in range(len(vals_for_this_row))
            ]

            max_len_for_this_row = max((len(v) for v in val_comma_for_this_row), default=0)
            inner_indent = indent + SQLFormatter.INDENT_1

            for v_idx, v_with_comma in enumerate(val_comma_for_this_row):
                col_name = cols[v_idx]
                pad_val = max_len_for_this_row - len(v_with_comma)
                if not v_with_comma.endswith(","):
                    pad_val += 1
                pad_val = max(0, pad_val)
                output_lines.append(f"{inner_indent}{v_with_comma}{' ' * (pad_val + 1)}-- {col_name}")

            output_lines.append(f"{indent})")

        if output_lines and not output_lines[-1].endswith(";"):
            output_lines[-1] = output_lines[-1] + ";"

        return "\n".join(output_lines)

    @staticmethod
    def format_insert_select_block(sql: str) -> str:
        """
        Format an INSERT INTO ... SELECT ... FROM ... statement, aligning SELECT fields
        with column names and preserving the remainder of the clause.

        :param sql: The full INSERT...SELECT statement ending with a semicolon.
        :return: A pretty-printed INSERT...SELECT statement or an error string on mismatch.
        """
        table_m = re.search(r"INSERT\s+INTO\s+([^\s(]+)", sql, re.IGNORECASE)
        cols_m = re.search(
            r"INSERT\s+INTO\s+[^\s(]+\s*\((.*?)\)\s*SELECT", sql, re.DOTALL | re.IGNORECASE
        )
        select_m = re.search(r"SELECT\s+(.*?)\s+FROM\s", sql, re.DOTALL | re.IGNORECASE)

        if not table_m or not cols_m or not select_m:
            return "❌ Invalid format. Expecting INSERT INTO <table>(...) SELECT ..."

        table_name = table_m.group(1)
        cols = [c.strip() for c in cols_m.group(1).split(",")]
        selects = [
            s.strip() for s in re.split(r",(?![^()]*\))", select_m.group(1))
        ]

        if len(cols) != len(selects):
            return f"❌ Column/select count mismatch ({len(cols)} vs {len(selects)})."

        indent = SQLFormatter.INDENT_1
        sel_comma = [selects[i] + ("," if i < len(selects) - 1 else "") for i in range(len(selects))]
        max_len = max((len(s) for s in sel_comma), default=0)

        lines = [f"INSERT INTO {table_name} ("]
        for i, col in enumerate(cols):
            comma = "," if i < len(cols) - 1 else ""
            lines.append(f"{indent}{col}{comma}")
        lines.append(") SELECT")

        for i, s in enumerate(sel_comma):
            lines.append(f"{indent}{s.ljust(max_len)}  -- {cols[i]}")

        rest = sql[sql.upper().find("FROM"):]
        lines.append(rest.strip())
        return "\n".join(lines)

    @staticmethod
    def extract_insert_statements(sql: str) -> List[str]:
        insert_values = re.findall(
            r"INSERT\s+INTO\s+[^\s(]+\s*\(.*?\)\s*VALUES\s*\(.*?\);",
            sql,
            re.DOTALL | re.IGNORECASE,
        )
        insert_selects = re.findall(
            r"INSERT\s+INTO\s+[^\s(]+\s*\([^)]*\)\s*SELECT\s+[^;]*?FROM[^;]*?;",
            sql,
            re.DOTALL | re.IGNORECASE,
        )
        return insert_values + insert_selects

    @staticmethod
    def format_create_table(sql: str) -> str:
        """
        Format a CREATE TABLE statement so that when multiple columns exist,
        each column is on its own line with proper indentation.
        :param sql: The CREATE TABLE statement (optionally ending with semicolon).
        :return: A single-line or multi-line formatted CREATE TABLE statement.
        """
        stripped = SQLFormatter._trim_semicolon(sql)
        m = re.match(
            r"(CREATE\s+TABLE\s+[^\(]+)\s*\((.*)\)\s*",
            stripped,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return sql.strip()

        header = m.group(1).strip()
        body = m.group(2).strip()
        cols = [c.strip() for c in re.split(r",(?![^(]*\))", body)]
        if len(cols) == 1:
            return re.sub(r"\s+", " ", sql.strip()) + ";"

        indent = SQLFormatter.INDENT_1
        out = [f"{header} ("]
        for i, col in enumerate(cols):
            comma = "," if i < len(cols) - 1 else ""
            out.append(f"{indent}{col}{comma}")
        out.append(");")
        return "\n".join(out)

    @staticmethod
    def format_alter_table(sql: str) -> str:
        """
        Format an ALTER TABLE statement. If only one action is present, collapse to a single line.
        If multiple comma-separated actions exist, place each action on its own line.

        :param sql: The ALTER TABLE statement (optionally ending with semicolon).
        :return: A formatted ALTER TABLE statement.
        """
        stripped = SQLFormatter._trim_semicolon(sql)
        m = re.match(r"(ALTER\s+TABLE\s+[^\s]+)\s+(.*)", stripped, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            return sql.strip()

        header = m.group(1).strip()
        rest = m.group(2).strip()
        actions = [a.strip() for a in re.split(r",(?![^(]*\))", rest)]
        if len(actions) == 1:
            single_line = SQLFormatter._collapse_whitespace(stripped)
            return f"{single_line} ;"

        indent = SQLFormatter.INDENT_1
        out = [header]
        for i, act in enumerate(actions):
            comma = "," if i < len(actions) - 1 else ""
            out.append(f"{indent}{act}{comma}")
        out.append(";")
        return "\n".join(out)

    @staticmethod
    def format_update_block(sql: str) -> str:
        """
        Reformat an UPDATE statement so that SET clauses and their assignments are each on their own line.
        :param sql: The full UPDATE statement ending with a semicolon.
        :return: A pretty-printed UPDATE statement.
        """
        joined = SQLFormatter._collapse_whitespace(sql)

        m = re.match(
            r"UPDATE\s+([^\s]+)\s+SET\s+(.*?)(?:\s+WHERE\s+(.*?))?;",
            joined,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return sql.strip()

        table = m.group(1).strip()
        assigns = m.group(2).strip()
        where_clause = m.group(3).strip() if m.group(3) else None

        parts = [p.strip() for p in re.split(r",(?=(?:[^']*'[^']*')*[^']*$)", assigns)]

        indent = SQLFormatter.INDENT_2
        out = [f"UPDATE {table}", f"{indent}SET"]

        for i, part in enumerate(parts):
            comma = "," if i < len(parts) - 1 else ""
            part = SQLFormatter.format_case_expression(part)
            lines = part.splitlines()

            if len(lines) == 1:
                out.append(f"{indent * 2}{lines[0]}{comma}")
            else:
                out.append(f"{indent * 2}{lines[0]}")
                for line in lines[1:-1]:
                    out.append(f"{indent * 3}{line}")
                last = lines[-1] + comma
                out.append(f"{indent * 3}{last}")

        if where_clause:
            out.append(f"WHERE {where_clause};")
        else:
            out.append(";")

        result = "\n".join(out)
        result = re.sub(r"\n;$", ";", result)
        return result

    @staticmethod
    def format_json_like_sql_field(field: str) -> str:
        try:
            parsed = json.loads(field)
            return json.dumps(parsed, indent=4)
        except json.JSONDecodeError:
            return field

    @staticmethod
    def format_set_block(sql: str) -> str:
        """
        Format one or more SET assignments so that each SET is aligned and column names are padded.
        If any RHS appears to be JSON (starts with '{' or '['), skip reformatting.

        :param sql: One or more SET statements, each optionally ending with semicolon.
        :return: A formatted multiline SET block or the original SQL on mismatch/JSON.
        """
        lines = sql.strip().splitlines()
        set_pattern = re.compile(
            r"^\s*SET\s+(@?[A-Z0-9_]+)\s*([:=]{1,2})\s*(.+?);?\s*$",
            re.IGNORECASE,
        )
        if not all(set_pattern.match(l) for l in lines):
            return sql

        parsed = []
        for line in lines:
            m = set_pattern.match(line)
            lhs, op, rhs = m.group(1), m.group(2), m.group(3).strip().rstrip(";")
            if rhs.startswith("{") or rhs.startswith("["):
                return sql
            parsed.append((lhs, op, rhs))

        max_lhs = max(len(lhs) for lhs, _, _ in parsed)
        out = []
        for lhs, op, rhs in parsed:
            out.append(f"SET {lhs.ljust(max_lhs)} {op} {rhs};")
        return "\n".join(out)

    @staticmethod
    def _format_embedded_json(stmt: str) -> str:
        """
        Detect embedded JSON strings (single-quoted) in an UPDATE statement,
        parse them, and replace with an indented JSON block.

        :param stmt: The UPDATE statement potentially containing JSON.
        :return: The statement with pretty-printed JSON sections.
        """

        def find_balanced_json(text: str, start: int) -> int:
            brace_level = 0
            in_str = False
            escape = False
            for i in range(start, len(text)):
                c = text[i]
                if c == "\\" and not escape:
                    escape = True
                    continue
                if c == '"' and not escape:
                    in_str = not in_str
                elif not in_str:
                    if c == "{":
                        brace_level += 1
                    elif c == "}":
                        brace_level -= 1
                        if brace_level == 0:
                            return i
                escape = False
            return -1

        pattern = re.compile(r"(=)\s*'({)", re.IGNORECASE)
        offset = 0
        while True:
            match = pattern.search(stmt, offset)
            if not match:
                break
            start_json = match.start(2)
            end_json = find_balanced_json(stmt, start_json)
            if end_json == -1:
                break

            json_str = stmt[start_json : end_json + 1]
            try:
                parsed = json.loads(json_str)
                pretty = json.dumps(parsed, indent=4)
                stmt = stmt[:start_json] + pretty + stmt[end_json + 1 :]
                offset = start_json + len(pretty)
            except json.JSONDecodeError:
                offset = end_json + 1
        return stmt

    @staticmethod
    def _indent_sql(block: str) -> str:
        """
        Prepend four spaces to each non-empty line in the given SQL block.

        :param block: A multi-line SQL string.
        :return: Indented SQL block.
        """
        lines = block.splitlines()
        return "\n".join("    " + line.strip() for line in lines if line.strip())

    @staticmethod
    def format_delete_block(sql: str) -> str:
        """
        Format a DELETE FROM ... WHERE ... statement so that each AND condition is on its own line.

        :param sql: The DELETE statement ending with a semicolon.
        :return: A pretty-printed DELETE statement or original SQL if no WHERE.
        """
        lines = ["DELETE FROM"]
        delete_match = re.match(r"DELETE\s+FROM\s+([^\s;]+)", sql, re.IGNORECASE)
        where_clause = re.split(r"\bWHERE\b", sql, maxsplit=1, flags=re.IGNORECASE)
        if delete_match:
            table = delete_match.group(1)
            lines[0] = f"DELETE FROM {table}"
            if len(where_clause) > 1:
                conditions = re.split(r"\s+AND\s+", where_clause[1].rstrip(";"), flags=re.IGNORECASE)
                lines.append("WHERE")
            else:
                return sql.strip()
        else:
            return sql.strip()

        for i, cond in enumerate(conditions):
            prefix = SQLFormatter.INDENT_1
            if i > 0:
                prefix += "AND "
            lines.append(f"{prefix}{cond.strip()}")

        return "\n".join(lines) + ";"

    @staticmethod
    def format_simple_single_line(sql: str) -> str:
        """
        Collapse all whitespace in a single-line statement (e.g., DROP TABLE, DROP INDEX).

        :param sql: The statement to collapse.
        :return: A single-line statement with no extra spaces.
        """
        return re.sub(r"\s+", " ", sql.strip())

    @staticmethod
    def format_case_expression(sql: str) -> str:
        """
        Expand inline CASE...END expressions into multiline form, with WHEN/THEN aligned
        and items inside IN(...) expanded as well.

        :param sql: An SQL snippet possibly containing a CASE expression.
        :return: The SQL with formatted CASE blocks.
        """
        def _case_repl(match: re.Match) -> str:
            full_block = match.group(0)
            inner = full_block[4:-3].strip()

            when_then_pairs = re.findall(
                r"WHEN\s+(?P<cond>.+?)\s+THEN\s+(?P<res>.+?)(?=(?:WHEN|ELSE|$))",
                inner,
                flags=re.IGNORECASE | re.DOTALL,
            )
            else_match = re.search(r"ELSE\s+(?P<else>.+)$", inner, flags=re.IGNORECASE | re.DOTALL)

            lines = ["CASE"]
            for cond, res in when_then_pairs:
                cond = cond.strip()
                res = res.strip()
                in_match = re.match(r"(.+?\bIN)\s*\((.+)\)$", cond, flags=re.IGNORECASE | re.DOTALL)
                if in_match:
                    in_prefix = in_match.group(1).strip()
                    in_list = in_match.group(2).strip()
                    items = [i.strip() for i in re.split(r",(?=(?:[^']*'[^']*')*[^']*$)", in_list)]
                    lines.append(f"    WHEN {in_prefix} (")
                    for j, item in enumerate(items):
                        comma = "," if j < len(items) - 1 else ""
                        lines.append(f"        {item}{comma}")
                    lines.append(f"    ) THEN {res}")
                else:
                    lines.append(f"    WHEN {cond} THEN {res}")

            if else_match:
                else_part = else_match.group("else").strip()
                lines.append(f"    ELSE {else_part}")

            lines.append("END")
            return "\n".join(lines)

        return re.sub(r"CASE\b.*?END\b", _case_repl, sql, flags=re.IGNORECASE | re.DOTALL)

    @staticmethod
    def smart_split_csv(s: str) -> List[str]:
        """
        Split a CSV string at top-level commas while respecting single quotes and parentheses.

        :param s: A comma-separated string, possibly containing nested parentheses or quoted commas.
        :return: A list of tokens.
        """
        parts = []
        current_chars = []
        in_single_quotes = False
        escape_next_char = False
        parentheses_level = 0

        for char in s:
            if escape_next_char:
                current_chars.append(char)
                escape_next_char = False
                continue
            if char == "\\":
                current_chars.append(char)
                escape_next_char = True
                continue
            if char == "'":
                in_single_quotes = not in_single_quotes
                current_chars.append(char)
                continue
            if not in_single_quotes:
                if char == "(":
                    parentheses_level += 1
                elif char == ")":
                    if parentheses_level > 0:
                        parentheses_level -= 1
                if char == "," and parentheses_level == 0:
                    parts.append("".join(current_chars).strip())
                    current_chars = []
                    continue
            current_chars.append(char)

        if current_chars or (not parts and s.strip() != ""):
            parts.append("".join(current_chars).strip())
        return [p for p in parts if p]
