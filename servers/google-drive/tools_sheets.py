from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS

from servers.google_drive.server import google_drive, _get_token, _sheets_service
from servers.google_drive._helpers import _get_sheet_id, _a1_to_grid_range, _hex_to_color


@google_drive.tool()
async def read_sheet(
    spreadsheet_id: str,
    range_notation: str = "Sheet1",
) -> list[list]:
    """Read values from a Google Sheet range."""
    token = _get_token()
    svc = _sheets_service(token)
    result = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_notation)
        .execute()
    )
    return result.get("values", [])


@google_drive.tool()
async def update_sheet(
    spreadsheet_id: str,
    range_notation: str,
    values: list[list],
) -> dict:
    """Write values to a Google Sheet range."""
    token = _get_token()
    svc = _sheets_service(token)
    return (
        svc.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_notation,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )


@google_drive.tool()
async def format_cells(
    spreadsheet_id: str,
    range_notation: str,
    bold: bool | None = None,
    italic: bool | None = None,
    font_family: str | None = None,
    font_size: float | None = None,
    foreground_color: str | None = None,
    background_color: str | None = None,
    horizontal_alignment: str | None = None,
    wrap_strategy: str | None = None,
    number_format_type: str | None = None,
    number_format_pattern: str | None = None,
) -> str:
    """Format cells in a Google Sheet range."""
    token = _get_token()
    svc = _sheets_service(token)
    grid_range = _a1_to_grid_range(svc, spreadsheet_id, range_notation)

    cell_format: dict = {}
    fields_list: list[str] = []

    text_format: dict = {}
    if bold is not None:
        text_format["bold"] = bold
        fields_list.append("userEnteredFormat.textFormat.bold")
    if italic is not None:
        text_format["italic"] = italic
        fields_list.append("userEnteredFormat.textFormat.italic")
    if font_family is not None:
        text_format["fontFamily"] = font_family
        fields_list.append("userEnteredFormat.textFormat.fontFamily")
    if font_size is not None:
        text_format["fontSize"] = font_size
        fields_list.append("userEnteredFormat.textFormat.fontSize")
    if foreground_color is not None:
        text_format["foregroundColor"] = _hex_to_color(foreground_color)
        fields_list.append("userEnteredFormat.textFormat.foregroundColor")
    if text_format:
        cell_format["textFormat"] = text_format

    if background_color is not None:
        cell_format["backgroundColor"] = _hex_to_color(background_color)
        fields_list.append("userEnteredFormat.backgroundColor")
    if horizontal_alignment is not None:
        cell_format["horizontalAlignment"] = horizontal_alignment
        fields_list.append("userEnteredFormat.horizontalAlignment")
    if wrap_strategy is not None:
        cell_format["wrapStrategy"] = wrap_strategy
        fields_list.append("userEnteredFormat.wrapStrategy")
    if number_format_type is not None:
        nf: dict = {"type": number_format_type}
        if number_format_pattern is not None:
            nf["pattern"] = number_format_pattern
        cell_format["numberFormat"] = nf
        fields_list.append("userEnteredFormat.numberFormat")

    if not fields_list:
        raise McpError(ErrorData(code=INVALID_PARAMS, message="Provide at least one format argument"))

    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"repeatCell": {
            "range": grid_range,
            "cell": {"userEnteredFormat": cell_format},
            "fields": ",".join(fields_list),
        }}]},
    ).execute()
    return f"Formatted cells in {range_notation}"


@google_drive.tool()
async def add_sheet(
    spreadsheet_id: str,
    title: str,
) -> str:
    """Add a new sheet tab to a Google Spreadsheet."""
    token = _get_token()
    svc = _sheets_service(token)
    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
    ).execute()
    return f"Added sheet '{title}'"


@google_drive.tool()
async def delete_sheet(
    spreadsheet_id: str,
    sheet_name: str,
) -> str:
    """Delete a sheet tab from a Google Spreadsheet by name."""
    token = _get_token()
    svc = _sheets_service(token)
    sheet_id = _get_sheet_id(svc, spreadsheet_id, sheet_name)
    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"deleteSheet": {"sheetId": sheet_id}}]},
    ).execute()
    return f"Deleted sheet '{sheet_name}'"


@google_drive.tool()
async def rename_sheet(
    spreadsheet_id: str,
    sheet_name: str,
    new_title: str,
) -> str:
    """Rename a sheet tab in a Google Spreadsheet."""
    token = _get_token()
    svc = _sheets_service(token)
    sheet_id = _get_sheet_id(svc, spreadsheet_id, sheet_name)
    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "title": new_title},
            "fields": "title",
        }}]},
    ).execute()
    return f"Renamed sheet '{sheet_name}' to '{new_title}'"


@google_drive.tool()
async def list_sheets(
    spreadsheet_id: str,
) -> list[dict]:
    """List all sheet tabs in a Google Spreadsheet."""
    token = _get_token()
    svc = _sheets_service(token)
    resp = svc.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets.properties"
    ).execute()
    return [
        {"sheetId": s["properties"]["sheetId"], "title": s["properties"]["title"]}
        for s in resp.get("sheets", [])
    ]


@google_drive.tool()
async def merge_cells(
    spreadsheet_id: str,
    range_notation: str,
    merge_type: str = "MERGE_ALL",
) -> str:
    """Merge cells in a Google Sheet range."""
    token = _get_token()
    svc = _sheets_service(token)
    grid_range = _a1_to_grid_range(svc, spreadsheet_id, range_notation)
    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"mergeCells": {"range": grid_range, "mergeType": merge_type}}]},
    ).execute()
    return f"Merged cells in {range_notation} ({merge_type})"


@google_drive.tool()
async def set_borders(
    spreadsheet_id: str,
    range_notation: str,
    sides: list[str],
    style: str = "SOLID",
    color: str = "#000000",
) -> str:
    """Set borders on a range of cells in a Google Sheet."""
    token = _get_token()
    svc = _sheets_service(token)
    grid_range = _a1_to_grid_range(svc, spreadsheet_id, range_notation)
    border = {"style": style, "color": _hex_to_color(color)}
    borders_spec: dict = {}
    for side in sides:
        borders_spec[side] = border
    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"updateBorders": {"range": grid_range, **borders_spec}}]},
    ).execute()
    return f"Set borders on {range_notation}"


@google_drive.tool()
async def add_conditional_format(
    spreadsheet_id: str,
    range_notation: str,
    condition_type: str,
    condition_value: str,
    background_color: str | None = None,
    foreground_color: str | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
) -> str:
    """Add a conditional formatting rule to a Google Sheet range."""
    token = _get_token()
    svc = _sheets_service(token)
    grid_range = _a1_to_grid_range(svc, spreadsheet_id, range_notation)

    fmt: dict = {}
    text_format: dict = {}
    if bold is not None:
        text_format["bold"] = bold
    if italic is not None:
        text_format["italic"] = italic
    if foreground_color is not None:
        text_format["foregroundColor"] = _hex_to_color(foreground_color)
    if text_format:
        fmt["textFormat"] = text_format
    if background_color is not None:
        fmt["backgroundColor"] = _hex_to_color(background_color)

    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addConditionalFormatRule": {
            "rule": {
                "ranges": [grid_range],
                "booleanRule": {
                    "condition": {
                        "type": condition_type,
                        "values": [{"userEnteredValue": condition_value}],
                    },
                    "format": fmt,
                },
            },
            "index": 0,
        }}]},
    ).execute()
    return f"Added conditional format rule to {range_notation}"


@google_drive.tool()
async def add_data_validation(
    spreadsheet_id: str,
    range_notation: str,
    validation_type: str,
    values: list[str],
) -> str:
    """Add data validation to a Google Sheet range."""
    token = _get_token()
    svc = _sheets_service(token)
    grid_range = _a1_to_grid_range(svc, spreadsheet_id, range_notation)

    if validation_type == "LIST":
        condition_type = "ONE_OF_LIST"
        show_custom_ui = True
    else:
        condition_type = validation_type
        show_custom_ui = False

    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"setDataValidation": {
            "range": grid_range,
            "rule": {
                "condition": {
                    "type": condition_type,
                    "values": [{"userEnteredValue": v} for v in values],
                },
                "showCustomUi": show_custom_ui,
                "strict": True,
            },
        }}]},
    ).execute()
    return f"Added data validation to {range_notation}"


@google_drive.tool()
async def add_named_range(
    spreadsheet_id: str,
    range_notation: str,
    name: str,
) -> str:
    """Add a named range to a Google Spreadsheet."""
    token = _get_token()
    svc = _sheets_service(token)
    grid_range = _a1_to_grid_range(svc, spreadsheet_id, range_notation)
    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addNamedRange": {
            "namedRange": {"name": name, "range": grid_range},
        }}]},
    ).execute()
    return f"Added named range '{name}' for {range_notation}"


@google_drive.tool()
async def protect_range(
    spreadsheet_id: str,
    range_notation: str,
    description: str = "",
    editors: list[str] | None = None,
) -> str:
    """Protect a range in a Google Spreadsheet from editing."""
    token = _get_token()
    svc = _sheets_service(token)
    grid_range = _a1_to_grid_range(svc, spreadsheet_id, range_notation)
    protected_range: dict = {"range": grid_range, "description": description}
    if editors is not None:
        protected_range["editors"] = {"users": editors}
    svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addProtectedRange": {"protectedRange": protected_range}}]},
    ).execute()
    return f"Protected range {range_notation}"


@google_drive.tool()
async def append_rows(
    spreadsheet_id: str,
    range_notation: str,
    values: list[list],
) -> dict:
    """Append rows to a Google Sheet without overwriting existing data."""
    token = _get_token()
    svc = _sheets_service(token)
    return svc.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=range_notation,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()


@google_drive.tool()
async def get_spreadsheet_info(
    spreadsheet_id: str,
) -> dict:
    """Get metadata about a Google Spreadsheet (title, sheets, row/column counts)."""
    token = _get_token()
    svc = _sheets_service(token)
    resp = svc.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="spreadsheetId,properties.title,sheets.properties",
    ).execute()
    return {
        "spreadsheetId": resp.get("spreadsheetId"),
        "title": resp.get("properties", {}).get("title"),
        "sheets": [
            {
                "sheetId": s["properties"]["sheetId"],
                "title": s["properties"]["title"],
                "rowCount": s["properties"].get("gridProperties", {}).get("rowCount"),
                "columnCount": s["properties"].get("gridProperties", {}).get("columnCount"),
            }
            for s in resp.get("sheets", [])
        ],
    }
