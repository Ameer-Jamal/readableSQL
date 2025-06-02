import json
import re


class SQLFormatter:
    @staticmethod
    def format_all(sql: str, pretty_json: bool = True) -> str:
        parts = re.split(r';\s*\n', sql.strip(), flags=re.DOTALL)
        if not parts or (len(parts) == 1 and not parts[0].strip()):
            # Handle empty or whitespace-only input
            return ""
        formatted_blocks = []

        for part_content in parts:
            part_content = part_content.strip()
            if not part_content:
                continue

            upper_part = part_content.upper()

            if re.search(r"INSERT\s+INTO\s+[^\s(]+\s*\(.*?\)\s*SELECT\b",
                         part_content,
                         re.IGNORECASE | re.DOTALL):
                formatted_part = SQLFormatter.format_insert_select_block(part_content + ";")

            elif upper_part.startswith("INSERT INTO"):
                formatted_part = SQLFormatter.format_insert_values_block(part_content + ";")

            elif upper_part.startswith("SET") and re.match(r'^SET\s+[@\w]+\s*[:=]', part_content, re.IGNORECASE):
                formatted_part = SQLFormatter.format_set_block(part_content + ";")

            elif upper_part.startswith("CREATE TABLE"):
                formatted_part = SQLFormatter.format_create_table(part_content + ";")

            elif upper_part.startswith("ALTER TABLE"):
                formatted_part = SQLFormatter.format_alter_table(part_content + ";")

            elif upper_part.startswith("UPDATE"):
                formatted_part = SQLFormatter.format_update_block(part_content + ";")
                if pretty_json:
                    formatted_part = SQLFormatter._format_embedded_json(formatted_part)

            elif upper_part.startswith("DELETE FROM"):
                formatted_part = SQLFormatter.format_delete_block(part_content + ";")

            elif upper_part.startswith("DROP TABLE") or upper_part.startswith("DROP INDEX"):
                formatted_part = SQLFormatter.format_simple_single_line(part_content + ";")

            else:
                # For unrecognized statements, just pass them through with their semicolon.
                if not part_content.strip().endswith(';'):
                    formatted_part = part_content + ';'
                else:
                    formatted_part = part_content

            formatted_part = SQLFormatter.format_case_expression(formatted_part)
            formatted_blocks.append(formatted_part)

        return "\n\n".join(formatted_blocks)  # Always join and return all blocks

    @staticmethod
    def format_insert_values_block(sql: str) -> str:
        table_m = re.search(r"INSERT\s+INTO\s+([^\s(]+)", sql, re.IGNORECASE)
        cols_m = re.search(r"INSERT\s+INTO\s+[^\s(]+\s*\((.*?)\)\s*VALUES", sql, re.DOTALL | re.IGNORECASE)
        values_block_m = re.search(r"VALUES\s*([\s\S]+?);", sql, re.IGNORECASE)

        if not table_m or not cols_m or not values_block_m:
            return f"❌ Invalid INSERT statement structure. Could not identify table, columns, or VALUES clause."

        table_name = table_m.group(1)
        cols_str = cols_m.group(1)
        cols = [c.strip() for c in cols_str.split(',')]

        values_content_raw = values_block_m.group(1).strip()
        individual_row_strings_content = []

        temp_delimiter = "<ROW_DELIMITER_TEMP_VALS>"
        processed_for_split = re.sub(r'\)\s*,\s*\(', f"){temp_delimiter}(", values_content_raw)

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
                return f"❌ Error parsing rows in VALUES. Ensure rows are correctly parenthesized and separated by commas (e.g., VALUES (r1v1, r1v2), (r2v1, r2v2))."

        if not individual_row_strings_content:
            if values_content_raw == "()":
                if not cols:
                    return f"INSERT INTO {table_name}\nVALUES ();"
                else:
                    return (
                        f"❌ Mismatch for table '{table_name}': {len(cols)} columns ({', '.join(cols)}) defined, but VALUES clause is empty '()'.")
            return f"❌ No value rows found in VALUES clause for table '{table_name}'."

        indent = "    "
        output_lines = [f"INSERT INTO {table_name} ("]
        for i, col in enumerate(cols):
            comma = ',' if i < len(cols) - 1 else ''
            output_lines.append(f"{indent}{col}{comma}")

        output_lines.append(") VALUES")

        for row_idx, row_values_str_content in enumerate(individual_row_strings_content):
            normalized_row_values_str = re.sub(r'\s*\n\s*', ' ', row_values_str_content.strip())
            vals_for_this_row = smart_split_csv(normalized_row_values_str)

            if not vals_for_this_row and not cols:
                if row_idx == 0:
                    output_lines.append(f"{indent}(")
                else:
                    output_lines.append(f"{indent},(")
                output_lines.append(f"{indent})")
                continue
            elif not vals_for_this_row and cols:
                return (
                    f"❌ Mismatch in row {row_idx + 1} for table '{table_name}': Values are empty, but {len(cols)} columns are defined: {', '.join(cols)}."
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

            max_len_for_this_row = 0
            if val_comma_for_this_row:
                max_len_for_this_row = max(len(v) for v in val_comma_for_this_row)

            inner_indent = indent + "    "

            for v_idx, v_with_comma in enumerate(val_comma_for_this_row):
                col_name = cols[v_idx]
                pad_val = max_len_for_this_row - len(v_with_comma)
                if not v_with_comma.endswith(','):
                    pad_val += 1
                pad_val = max(0, pad_val)
                output_lines.append(f"{inner_indent}{v_with_comma}{' ' * (pad_val + 1)}-- {col_name}")

            output_lines.append(f"{indent})")

        if output_lines and not output_lines[-1].endswith(";"):
            output_lines[-1] = output_lines[-1] + ";"

        return "\n".join(output_lines)

    @staticmethod
    def format_insert_select_block(sql: str) -> str:
        # Extract INSERT INTO table and columns
        table_m = re.search(r"INSERT\s+INTO\s+([^\s(]+)", sql, re.IGNORECASE)
        cols_m = re.search(r"INSERT\s+INTO\s+[^\s(]+\s*\((.*?)\)\s*SELECT", sql, re.DOTALL | re.IGNORECASE)
        select_m = re.search(r"SELECT\s+(.*?)\s+FROM\s", sql, re.DOTALL | re.IGNORECASE)

        if not table_m or not cols_m or not select_m:
            return "❌ Invalid format. Expecting INSERT INTO <table>(...) SELECT ..."

        table_name = table_m.group(1)
        cols = [c.strip() for c in cols_m.group(1).split(',')]
        selects = [s.strip() for s in re.split(r',(?![^()]*\))', select_m.group(1))]

        if len(cols) != len(selects):
            return f"❌ Column/select count mismatch ({len(cols)} vs {len(selects)})."

        indent = "    "
        sel_comma = [selects[i] + ("," if i < len(selects) - 1 else "") for i in range(len(selects))]
        max_len = max(len(s) for s in sel_comma)

        lines = [f"INSERT INTO {table_name} ("]
        for i, col in enumerate(cols):
            comma = ',' if i < len(cols) - 1 else ''
            lines.append(f"{indent}{col}{comma}")
        lines.append(") SELECT")

        for i, s in enumerate(sel_comma):
            lines.append(f"{indent}{s.ljust(max_len)}  -- {cols[i]}")

        rest = sql[sql.upper().find("FROM"):]
        lines.append(rest.strip())
        return "\n".join(lines)

    @staticmethod
    def extract_insert_statements(sql: str) -> list[str]:
        insert_values = re.findall(
            r"INSERT\s+INTO\s+[^\s(]+\s*\(.*?\)\s*VALUES\s*\(.*?\);",
            sql,
            re.DOTALL | re.IGNORECASE
        )
        insert_selects = re.findall(
            r"INSERT\s+INTO\s+[^\s(]+\s*\(.*?\)\s*SELECT\s+.*?FROM.*?;",
            sql,
            re.DOTALL | re.IGNORECASE
        )
        return insert_values + insert_selects

    @staticmethod
    def format_create_table(sql: str) -> str:
        """
        If there is exactly one CREATE TABLE clause, collapse whitespace:
          CREATE TABLE foo(col1 TYPE, col2 TYPE);
        → (no change but trimmed/collapsed)
        If there are multiple columns (comma-separated), break out on separate lines:
          CREATE TABLE foo (
              col1 TYPE,
              col2 TYPE,
              …
          );
        """
        stripped = sql.strip().rstrip(';')
        # Try to match: CREATE TABLE <name> ( … )
        m = re.match(
            r'(CREATE\s+TABLE\s+[^\(]+)\s*\((.*)\)\s*',
            stripped,
            flags=re.IGNORECASE | re.DOTALL
        )
        if not m:
            return sql.strip()

        header = m.group(1).strip()
        body = m.group(2).strip()
        # Split columns on top-level commas
        cols = [c.strip() for c in re.split(r',(?![^(]*\))', body)]
        # If there's only one column definition, just collapse whitespace and return one line
        if len(cols) == 1:
            return re.sub(r'\s+', ' ', sql.strip()) + ";"

        # Otherwise, multi-line format
        indent = "    "
        out = [f"{header} ("]
        for i, col in enumerate(cols):
            comma = ',' if i < len(cols) - 1 else ''
            out.append(f"{indent}{col}{comma}")
        out.append(");")
        return "\n".join(out)

    @staticmethod
    def format_alter_table(sql: str) -> str:
        """
        If there’s exactly one ALTER action, collapse whitespace:
          ALTER TABLE foo ADD COLUMN bar int ;
        → "ALTER TABLE foo ADD COLUMN bar int ;"
        If there are multiple actions (comma-separated), break them onto separate lines:
          ALTER TABLE foo
              ADD COLUMN bar int,
              DROP COLUMN baz;
        """
        stripped = sql.strip().rstrip(';')  # remove any existing trailing semicolons
        m = re.match(
            r'(ALTER\s+TABLE\s+[^\s]+)\s+(.*)',
            stripped,
            flags=re.IGNORECASE | re.DOTALL
        )
        if not m:
            return sql.strip()

        header = m.group(1).strip()
        rest = m.group(2).strip()
        # Split on top-level commas:
        actions = [a.strip() for a in re.split(r',(?![^(]*\))', rest)]
        # If only one action, collapse whitespace and return one line
        if len(actions) == 1:
            single_line = re.sub(r'\s+', ' ', stripped).strip()
            return single_line + " ;"

        # Otherwise, multi-line format
        indent = "    "
        out = [header]
        for i, act in enumerate(actions):
            comma = ',' if i < len(actions) - 1 else ''
            out.append(f"{indent}{act}{comma}")
        out.append(";")
        return "\n".join(out)

    @staticmethod
    def format_update_block(sql: str) -> str:
        """
        Reformats:
          UPDATE foo SET col1 = val1, col2 = val2 WHERE cond;
        into:
          UPDATE foo
            SET
              col1 = val1,
              col2 = val2
          WHERE cond;
        (Does not itself pretty-print JSON; JSON should be handled by format_all.)
        """
        # 1) Collapse all lines into one string
        joined = " ".join(line.strip() for line in sql.strip().splitlines())

        # 2) Match UPDATE <table> SET <assigns> WHERE <cond>
        m = re.match(
            r'UPDATE\s+([^\s]+)\s+SET\s+(.*?)\s+WHERE\s+(.*)',
            joined,
            flags=re.IGNORECASE | re.DOTALL
        )
        if not m:
            return sql.strip()

        table = m.group(1).strip()
        assigns = m.group(2).strip().rstrip(';')
        where = m.group(3).strip().rstrip(';')

        # 3) Split assignments on commas not inside braces/brackets
        parts = [p.strip() for p in re.split(r',(?![^{\[]*[}\]])', assigns)]

        # 4) Build multi-line output
        indent = "  "
        out = [f"UPDATE {table}", f"{indent}SET"]
        for i, part in enumerate(parts):
            comma = "," if i < len(parts) - 1 else ""
            out.append(f"{indent * 2}{part}{comma}")
        out.append(f"WHERE {where};")
        return "\n".join(out)

    @staticmethod
    def format_json_like_sql_field(field: str) -> str:
        try:
            import json
            parsed = json.loads(field)
            return json.dumps(parsed, indent=4)
        except:
            return field

    @staticmethod
    def format_set_block(sql: str) -> str:
        lines = sql.strip().splitlines()
        parsed = []

        set_pattern = re.compile(
            r"^\s*SET\s+(@?[A-Z0-9_]+)\s*([:=]{1,2})\s*(.+?);?\s*$",
            re.IGNORECASE
        )
        # only pure SET‐lines
        if not all(set_pattern.match(l) for l in lines):
            return sql

        for line in lines:
            m = set_pattern.match(line)
            lhs, op, rhs = m.group(1), m.group(2), m.group(3).strip().rstrip(';')
            # skip JSON‐like values
            if rhs.startswith('{') or rhs.startswith('['):
                return sql
            parsed.append((lhs, op, rhs))

        max_lhs = max(len(lhs) for lhs, _, _ in parsed)

        out = []
        for lhs, op, rhs in parsed:
            out.append(f"SET {lhs.ljust(max_lhs)} {op} {rhs};")
        return "\n".join(out)

    @staticmethod
    def _format_insert_select_block(stmt: str) -> str:
        parts = re.split(r"\bSELECT\b", stmt, flags=re.IGNORECASE)
        if len(parts) < 2:
            return stmt + ';'

        before_select = parts[0].strip()
        select_clause = "SELECT " + parts[1].strip()

        return before_select + "\n" + SQLFormatter._indent_sql(select_clause) + ";"

    @staticmethod
    def _format_create_table(stmt: str) -> str:
        header_match = re.match(r"(CREATE\s+TABLE\s+[^\(]+)\s*\((.*)\)", stmt, re.IGNORECASE | re.DOTALL)
        if not header_match:
            return stmt + ';'

        header = header_match.group(1)
        body = header_match.group(2)
        lines = [l.strip() for l in re.split(r',(?![^\(]*\))', body.strip()) if l.strip()]
        formatted_body = ',\n    '.join(lines)

        return f"{header} (\n    {formatted_body}\n);"

    @staticmethod
    def _format_embedded_json(stmt: str) -> str:
        def find_balanced_json(text, start):
            brace_level = 0
            in_str = False
            escape = False
            for i in range(start, len(text)):
                c = text[i]
                if c == '\\' and not escape:
                    escape = True
                    continue
                if c == '"' and not escape:
                    in_str = not in_str
                elif not in_str:
                    if c == '{':
                        brace_level += 1
                    elif c == '}':
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

            json_str = stmt[start_json:end_json + 1]
            try:
                parsed = json.loads(json_str)
                pretty = json.dumps(parsed, indent=4)
                stmt = stmt[:start_json] + pretty + stmt[end_json + 1:]
                offset = start_json + len(pretty)
            except json.JSONDecodeError:
                offset = end_json + 1
        return stmt

    @staticmethod
    def _indent_sql(block: str) -> str:
        lines = block.splitlines()
        return '\n'.join('    ' + line.strip() for line in lines if line.strip())

    @staticmethod
    def format_delete_block(sql: str) -> str:
        lines = ["DELETE FROM"]
        delete_match = re.match(r"DELETE\s+FROM\s+([^\s;]+)", sql, re.IGNORECASE)
        where_clause = re.split(r"\bWHERE\b", sql, maxsplit=1, flags=re.IGNORECASE)
        if delete_match:
            table = delete_match.group(1)
            lines[0] = f"DELETE FROM {table}"
            if len(where_clause) > 1:
                # split on AND, then re-emit each condition with "AND " on lines ≥1
                conditions = re.split(r'\s+AND\s+', where_clause[1].rstrip(';'), flags=re.IGNORECASE)
                lines.append("WHERE")
            else:
                # no WHERE at all → just return without formatting
                return sql.strip()
        else:
            return sql.strip()

        for i, cond in enumerate(conditions):
            prefix = "    "
            if i > 0:
                prefix += "AND "
            lines.append(f"{prefix}{cond.strip()}")

        return "\n".join(lines) + ";"

    @staticmethod
    def format_simple_single_line(sql: str) -> str:
        return re.sub(r'\s+', ' ', sql.strip())

    @staticmethod
    def format_case_expression(sql: str) -> str:
        def _case_repl(match):
            full_block = match.group(0)
            inner = full_block[4:-3].strip()

            when_then_pairs = re.findall(
                r"WHEN\s+(?P<cond>.+?)\s+THEN\s+(?P<res>.+?)(?=(?:WHEN|ELSE|$))",
                inner,
                flags=re.IGNORECASE | re.DOTALL
            )

            else_match = re.search(r"ELSE\s+(?P<else>.+)$", inner, flags=re.IGNORECASE | re.DOTALL)

            lines = ["CASE"]
            for cond, res in when_then_pairs:
                lines.append(f"    WHEN {cond.strip()} THEN {res.strip()}")

            if else_match:
                else_part = else_match.group("else").strip()
                lines.append(f"    ELSE {else_part}")

            lines.append("END")
            return "\n".join(lines)

        # Apply to every CASE…END (non-greedy so it stops at the first END)
        return re.sub(r"CASE\b.*?END\b", _case_repl, sql, flags=re.IGNORECASE | re.DOTALL)


def smart_split_csv(s: str) -> list[str]:
    parts = []
    current_chars = []
    in_single_quotes = False
    escape_next_char = False
    parentheses_level = 0
    for char_idx, char in enumerate(s):
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
            if char == '(':
                parentheses_level += 1
            elif char == ')':
                if parentheses_level > 0:
                    parentheses_level -= 1
            if char == "," and parentheses_level == 0:
                parts.append("".join(current_chars).strip())
                current_chars = []
                continue
        current_chars.append(char)
    if current_chars or not parts and not s.strip() == "":  # Add last part
        parts.append("".join(current_chars).strip())
    return [p for p in parts if p]  # Filter out empty strings that might result from trailing commas etc.
