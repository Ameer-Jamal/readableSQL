import json
import re


class SQLFormatter:
    @staticmethod
    def format_all(sql: str, pretty_json: bool = True) -> str:
        parts = re.split(r';\s*\n', sql.strip(), flags=re.DOTALL)
        formatted_blocks = []

        for part in parts:
            part = part.strip()
            if not part:
                continue
            upper = part.upper()

            # INSERT ... SELECT
            if upper.startswith("INSERT INTO") and "SELECT" in upper:
                formatted_blocks.append(
                    SQLFormatter.format_insert_select_block(part + ';')
                )

            # INSERT ... VALUES
            elif upper.startswith("INSERT INTO"):
                formatted_blocks.append(
                    SQLFormatter.format_insert_values_block(part + ';')
                )

            # Pure SET var = ...;  → our new, strict formatter
            elif upper.startswith("SET") and re.match(r'^SET\s+[@\w]+\s*[:=]', part.strip(), re.IGNORECASE):
                formatted_blocks.append(
                    SQLFormatter.format_set_block(part + ';')
                )

            # CREATE TABLE
            elif upper.startswith("CREATE TABLE"):
                formatted_blocks.append(
                    SQLFormatter.format_create_table(part + ';')
                )

            # ALTER TABLE
            elif upper.startswith("ALTER TABLE"):
                formatted_blocks.append(
                    SQLFormatter.format_alter_table(part + ';')
                )

            elif upper.startswith("UPDATE"):
                # first do your strict UPDATE formatting
                upd = SQLFormatter.format_update_block(part + ';')
                # only pretty‐print embedded JSON if the flag is on
                if pretty_json:
                    upd = SQLFormatter._format_embedded_json(upd)
                formatted_blocks.append(upd)

            else:
                formatted_blocks.append(part + ';')

        return "\n\n".join(formatted_blocks)

    @staticmethod
    def format_insert_values_block(sql: str) -> str:
        table_m = re.search(r"INSERT\s+INTO\s+([^\s(]+)", sql, re.IGNORECASE)
        cols_m = re.search(r"INSERT\s+INTO\s+[^\s(]+\s*\((.*?)\)\s*VALUES", sql, re.DOTALL | re.IGNORECASE)
        vals_m = re.search(r"VALUES\s*\(\s*(.*?)\s*\)\s*;", sql, re.DOTALL | re.IGNORECASE)

        if not table_m or not cols_m or not vals_m:
            return "❌ Invalid format. Expecting INSERT INTO <table>(...) VALUES (...);"

        table_name = table_m.group(1)
        cols = [c.strip() for c in cols_m.group(1).split(',')]
        vals = [v.strip() for v in re.split(r',(?![^()]*\))', vals_m.group(1))]

        if len(cols) != len(vals):
            return (
                f"❌ Column/value count mismatch ({len(cols)} vs {len(vals)}).\n\n"
                f"❌Columns: {cols}\n\n❌Values: {vals}"
            )

        indent = "    "
        val_comma = [vals[i] + ("," if i < len(vals) - 1 else "") for i in range(len(vals))]
        max_len = max(len(v) for v in val_comma)

        lines = [f"INSERT INTO {table_name} ("]
        for i, col in enumerate(cols):
            comma = ',' if i < len(cols) - 1 else ''
            lines.append(f"{indent}{col}{comma}")
        lines.append(") VALUES (")

        for i, v in enumerate(val_comma):
            lines.append(f"{indent}{v.ljust(max_len)}  -- {cols[i]}")

        lines.append(");")
        return "\n".join(lines)

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
        in_assign = False
        buffer = []

        # stricter: only lines starting “SET <var> =” or “SET <var> :=”
        start_pattern = re.compile(r'^SET\s+[@\w]+\s*[:=]', re.IGNORECASE)
        # splits on commas not inside JSON braces
        split_commas = lambda text: re.split(r',(?![^{}]*\})', text)

        for line in lines:
            stripped = line.strip()
            if start_pattern.match(stripped):
                # begin assignment block
                in_assign = True
                # drop the “SET ” prefix, keep the rest
                buffer.append(stripped[len(stripped.split(None, 1)[0]):].strip())
            elif in_assign and re.match(r'^[@\w]', stripped):
                # continuation line of assignments
                buffer.append(stripped)
            else:
                # flush any buffered assignments
                if in_assign:
                    formatted.append("  SET")
                    joint = ' '.join(buffer)
                    parts = split_commas(joint)
                    for part in parts:
                        formatted.append(f"    {part.strip()},")
                    # remove trailing comma on last assignment
                    formatted[-1] = formatted[-1].rstrip(',')
                    buffer.clear()
                    in_assign = False
                formatted.append(line)

        # flush at EOF if still in_assign
        if in_assign:
            formatted.append("  SET")
            joint = ' '.join(buffer)
            parts = split_commas(joint)
            for part in parts:
                formatted.append(f"    {part.strip()},")
            formatted[-1] = formatted[-1].rstrip(',')

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
        skip_json = lambda v: v.strip().startswith('{') or v.strip().startswith('[')

        set_pattern = re.compile(
            r"^\s*SET\s+(@?[A-Z0-9_]+)\s*([:=]{1,2})\s*(.+);?$",
            re.IGNORECASE
        )

        # Only treat as set block if all lines match the `SET var = value` format
        is_pure_set_block = all(set_pattern.match(line.strip()) for line in lines)

        if not is_pure_set_block:
            return sql  # Return original if this is not a pure SET block

        for line in lines:
            m = set_pattern.match(line.strip())
            if m:
                lhs, op, rhs = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
                if skip_json(rhs):
                    return sql  # skip formatting if we hit JSON-ish content
                parsed.append((lhs, op, rhs))

        max_lhs_len = max(len(lhs) for lhs, _, _ in parsed)
        max_op_len = max(len(op) for _, op, _ in parsed)

        formatted_lines = [
            f"SET {lhs.ljust(max_lhs_len)} {op.ljust(max_op_len)} {rhs};"
            for lhs, op, rhs in parsed
        ]
        return "\n".join(formatted_lines)

    @staticmethod
    def _format_insert_values_block(stmt: str) -> str:
        table_match = re.search(r"INSERT\s+INTO\s+([^\s(]+)", stmt, re.IGNORECASE)
        cols_match = re.search(r"\((.*?)\)\s*VALUES", stmt, re.IGNORECASE | re.DOTALL)
        values_match = re.search(r"VALUES\s*\((.*)\)", stmt, re.IGNORECASE | re.DOTALL)

        if not table_match or not cols_match or not values_match:
            return stmt + ';'

        cols = [c.strip() for c in cols_match.group(1).split(',')]
        values = re.split(r',(?![^()]*\))', values_match.group(1))
        values = [v.strip() for v in values]

        formatted = f"INSERT INTO {table_match.group(1)} (\n    " + ',\n    '.join(
            cols) + "\n)\nVALUES (\n    " + ',\n    '.join(values) + "\n);"
        return formatted

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
        def replacer(m):
            prefix = m.group('prefix')
            raw = m.group('json')
            try:
                obj = json.loads(raw)
                pretty = json.dumps(obj, indent=4)
                return f"{prefix}'{pretty}'"
            except Exception:
                return m.group(0)

        pattern = r"""(?P<prefix>\bSET\b.*?=\s*|UPDATE\s+\w+\s+SET\s+\w+\s*=\s*)'(?P<json>\{.*?\})'"""
        return re.sub(pattern, replacer, stmt, flags=re.IGNORECASE | re.DOTALL)

    @staticmethod
    def _indent_sql(block: str) -> str:
        lines = block.splitlines()
        return '\n'.join('    ' + line.strip() for line in lines if line.strip())
