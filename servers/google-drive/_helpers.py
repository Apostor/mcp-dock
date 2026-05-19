from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS


def _hex_to_color(hex_color: str) -> dict:
    """Convert '#RRGGBB' to {"red": float, "green": float, "blue": float}."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise McpError(ErrorData(code=INVALID_PARAMS, message=f"Invalid hex color: {hex_color!r}"))
    return {
        "red": int(h[0:2], 16) / 255.0,
        "green": int(h[2:4], 16) / 255.0,
        "blue": int(h[4:6], 16) / 255.0,
    }


def _col_letter_to_index(col: str) -> int:
    """Convert column letter(s) to 0-based index (A→0, B→1, Z→25, AA→26)."""
    result = 0
    for ch in col.upper():
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


def _get_sheet_id(svc, spreadsheet_id: str, sheet_name: str) -> int:
    """Return the integer sheetId for the named tab. Raises McpError if not found."""
    resp = svc.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets.properties"
    ).execute()
    for sheet in resp.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == sheet_name:
            return props["sheetId"]
    raise McpError(
        ErrorData(
            code=INVALID_PARAMS,
            message=f"Sheet '{sheet_name}' not found in spreadsheet '{spreadsheet_id}'",
        )
    )


def _a1_to_grid_range(svc, spreadsheet_id: str, range_notation: str) -> dict:
    """Parse 'Sheet1!A1:B3' into a GridRange dict with numeric indices."""
    if "!" in range_notation:
        sheet_name, cell_range = range_notation.split("!", 1)
    else:
        sheet_name = range_notation
        cell_range = None

    sheet_id = _get_sheet_id(svc, spreadsheet_id, sheet_name)
    grid: dict = {"sheetId": sheet_id}

    if cell_range:
        start_cell, _, end_cell = cell_range.partition(":")
        end_cell = end_cell or start_cell

        def _parse(cell: str) -> tuple[int, int]:
            col_str, row_str = "", ""
            for ch in cell:
                (col_str if ch.isalpha() else row_str).__class__  # satisfy linter
                if ch.isalpha():
                    col_str += ch
                else:
                    row_str += ch
            return (
                _col_letter_to_index(col_str) if col_str else 0,
                (int(row_str) - 1) if row_str else 0,
            )

        sc, sr = _parse(start_cell)
        ec, er = _parse(end_cell)
        grid["startRowIndex"] = sr
        grid["endRowIndex"] = er + 1
        grid["startColumnIndex"] = sc
        grid["endColumnIndex"] = ec + 1

    return grid


def _find_text_ranges(
    content: list,
    text: str,
    occurrence_index: int | None = None,
) -> list[tuple[int, int]]:
    """Scan Docs body content for all occurrences of text.

    Returns list of (startIndex, endIndex) pairs. If occurrence_index is
    provided (0-based), returns only that match. Raises McpError if out of range.
    """
    matches: list[tuple[int, int]] = []
    for element in content:
        paragraph = element.get("paragraph", {})
        elements = paragraph.get("elements", [])
        para_text = ""
        para_start: int | None = None
        for pe in elements:
            run_content = pe.get("textRun", {}).get("content", "")
            start_idx = pe.get("startIndex", 0)
            if para_start is None:
                para_start = start_idx
            para_text += run_content
        if para_start is None:
            continue
        pos = 0
        while True:
            idx = para_text.find(text, pos)
            if idx == -1:
                break
            matches.append((para_start + idx, para_start + idx + len(text)))
            pos = idx + 1

    if occurrence_index is not None:
        if occurrence_index < 0 or occurrence_index >= len(matches):
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=(
                        f"occurrence_index {occurrence_index} out of range "
                        f"(found {len(matches)} matches)"
                    ),
                )
            )
        return [matches[occurrence_index]]
    return matches


def _find_table_by_index(content: list, table_index: int) -> dict:
    """Return the nth element with a 'table' key (0-based). Raises McpError if out of range."""
    tables = [el for el in content if "table" in el]
    if table_index < 0 or table_index >= len(tables):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"table_index {table_index} out of range (found {len(tables)} tables)",
            )
        )
    return tables[table_index]
