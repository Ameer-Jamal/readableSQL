import json
import re


class SQLFormatter:
    @staticmethod
    def format_all(sql: str, pretty_json: bool = True) -> str:
        parts = re.split(r';\s*\n', sql.strip(), flags=re.DOTALL)
        if not parts or (len(parts) == 1 and not parts[0].strip()):  # Handle empty or whitespace-only input
            return ""

        formatted_blocks = []

        for part_content in parts:
            part_content = part_content.strip()
            if not part_content:
                continue

            upper_part = part_content.upper()

            # INSERT ... SELECT
            if re.search(r"INSERT\s+INTO\s+[^\s(]+\s*\(.*?\)\s*SELECT\b", part_content, re.IGNORECASE | re.DOTALL):
                formatted_part = SQLFormatter.format_insert_select_block(
                    part_content + ";")  # Add ; for consistent parsing

            # INSERT ... VALUES
            elif upper_part.startswith("INSERT INTO"):
                formatted_part = SQLFormatter.format_insert_values_block(part_content + ";")

            elif upper_part.startswith("SET") and re.match(r'^SET\s+[@\w]+\s*[:=]', part_content, re.IGNORECASE):
                formatted_part = SQLFormatter.format_set_block(part_content + ";")

            elif upper_part.startswith("CREATE TABLE"):
                formatted_part = SQLFormatter.format_create_table(part_content + ";")

            elif upper_part.startswith("ALTER TABLE"):
                formatted_part = SQLFormatter.format_alter_table(part_content + ";")

            elif upper_part.startswith("UPDATE"):
                upd = SQLFormatter.format_update_block(part_content + ";")
                if pretty_json:
                    upd = SQLFormatter._format_embedded_json(upd)
                formatted_part = upd

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
        lines = sql.splitlines()
        formatted = []
        indent = "    "
        for line in lines:
            stripped = line.strip()
            if stripped.upper().startswith("CREATE TABLE"):
                formatted.append(stripped)
            elif stripped.startswith("(") or stripped.endswith(",") or stripped.endswith(")"):
                formatted.append(indent + stripped)
            else:
                formatted.append(indent + stripped + ',')
        return "\n".join(formatted)

    @staticmethod
    def format_alter_table(sql: str) -> str:
        return re.sub(r'\s+', ' ', sql.strip(), flags=re.MULTILINE)

    @staticmethod
    def format_update_block(sql: str) -> str:
        lines = sql.splitlines()
        formatted = []
        buffer = []
        in_assign = False

        start_re = re.compile(r'^SET\s+[@\w]+\s*[:=]', re.IGNORECASE)
        cont_re = re.compile(r'^@?\w+\s*[:=]')

        for line in lines:
            stripped = line.strip()
            if start_re.match(stripped):
                in_assign = True
                # drop leading "SET"
                rest = stripped[len(stripped.split(None, 1)[0]):].strip()
                buffer.append(rest)
            elif in_assign and cont_re.match(stripped):
                buffer.append(stripped)
            else:
                if in_assign:
                    formatted.append("  SET")
                    joint = ' '.join(buffer)
                    parts = re.split(r',(?![^{}]*\})', joint)
                    for p in parts[:-1]:
                        formatted.append(f"    {p.strip()},")
                    # last part without trailing comma
                    formatted.append(f"    {parts[-1].strip()}")
                    buffer.clear()
                    in_assign = False
                formatted.append(line)

        if in_assign:
            formatted.append("  SET")
            joint = ' '.join(buffer)
            parts = re.split(r',(?![^{}]*\})', joint)
            for p in parts[:-1]:
                formatted.append(f"    {p.strip()},")
            formatted.append(f"    {parts[-1].strip()}")

        return "\n".join(formatted)

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
        def repl(m):
            prefix, raw = m.group('prefix'), m.group('json')
            try:
                obj = json.loads(raw)
                pretty = json.dumps(obj, indent=4)
                return f"{prefix}'{pretty}'"
            except:
                return m.group(0)

        pattern = r"""(?P<prefix>\bSET\b.*?=\s*|UPDATE\s+\w+\s+SET\s+\w+\s*=\s*)'(?P<json>\{.*?\})'"""
        return re.sub(pattern, repl, stmt, flags=re.IGNORECASE | re.DOTALL)

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
                conditions = re.split(r'\s+AND\s+', where_clause[1].rstrip(';'), flags=re.IGNORECASE)
                lines.append("WHERE")
                lines += [f"    {cond.strip()}" for cond in conditions]
        else:
            return sql.strip()
        return "\n".join(lines) + ";"

    @staticmethod
    def format_simple_single_line(sql: str) -> str:
        return sql.strip()

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
    if current_chars or not parts and not s.strip() == "": # Add last part
        parts.append("".join(current_chars).strip())
    return [p for p in parts if p] # Filter out empty strings that might result from trailing commas etc.
    return parts