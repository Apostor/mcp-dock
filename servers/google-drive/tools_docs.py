from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS

from servers.google_drive.server import google_drive, _get_token, _docs_service
from servers.google_drive._helpers import _find_text_ranges, _find_table_by_index, _hex_to_color


@google_drive.tool()
async def read_doc(
    document_id: str,
) -> str:
    """Read the plain-text content of a Google Doc."""
    token = _get_token()
    svc = _docs_service(token)
    doc = svc.documents().get(documentId=document_id).execute()
    body = doc.get("body", {})
    text_parts = []
    for element in body.get("content", []):
        for para_element in element.get("paragraph", {}).get("elements", []):
            text_run = para_element.get("textRun", {})
            text_parts.append(text_run.get("content", ""))
    return "".join(text_parts)


@google_drive.tool()
async def update_doc(
    document_id: str,
    content: str,
) -> dict:
    """Replace all content in a Google Doc with the given text."""
    token = _get_token()
    svc = _docs_service(token)
    doc = svc.documents().get(documentId=document_id).execute()
    end_index = doc["body"]["content"][-1]["endIndex"] - 1
    requests = []
    if end_index > 1:
        requests.append({"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index}}})
    requests.append({"insertText": {"location": {"index": 1}, "text": content}})
    return svc.documents().batchUpdate(
        documentId=document_id, body={"requests": requests}
    ).execute()


@google_drive.tool()
async def get_doc_content(
    document_id: str,
) -> list[dict]:
    """Get structured content of a Google Doc with text indices."""
    token = _get_token()
    svc = _docs_service(token)
    doc = svc.documents().get(documentId=document_id).execute()
    body_content = doc.get("body", {}).get("content", [])
    result = []
    for element in body_content:
        if "paragraph" in element:
            result.append({
                "startIndex": element.get("startIndex"),
                "endIndex": element.get("endIndex"),
                "type": "paragraph",
                "elements": element["paragraph"].get("elements", []),
            })
        elif "table" in element:
            result.append({
                "startIndex": element.get("startIndex"),
                "endIndex": element.get("endIndex"),
                "type": "table",
                "rows": element["table"].get("tableRows", []),
            })
        elif "sectionBreak" in element:
            result.append({
                "startIndex": element.get("startIndex"),
                "endIndex": element.get("endIndex"),
                "type": "sectionBreak",
            })
        else:
            result.append({
                "startIndex": element.get("startIndex"),
                "endIndex": element.get("endIndex"),
                "type": "other",
            })
    return result


@google_drive.tool()
async def format_doc_text(
    document_id: str,
    text_to_find: str | None = None,
    occurrence_index: int | None = None,
    start_index: int | None = None,
    end_index: int | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
    underline: bool | None = None,
    strikethrough: bool | None = None,
    font_family: str | None = None,
    font_size: float | None = None,
    foreground_color: str | None = None,
    background_color: str | None = None,
) -> str:
    """Apply text formatting in a Google Doc. Use text_to_find or start_index+end_index."""
    token = _get_token()
    svc = _docs_service(token)

    if text_to_find is not None:
        doc = svc.documents().get(documentId=document_id).execute()
        content = doc.get("body", {}).get("content", [])
        ranges = _find_text_ranges(content, text_to_find, occurrence_index)
    elif start_index is not None and end_index is not None:
        ranges = [(start_index, end_index)]
    else:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message="Provide text_to_find or start_index+end_index")
        )

    text_style: dict = {}
    fields: list[str] = []
    if bold is not None:
        text_style["bold"] = bold
        fields.append("bold")
    if italic is not None:
        text_style["italic"] = italic
        fields.append("italic")
    if underline is not None:
        text_style["underline"] = underline
        fields.append("underline")
    if strikethrough is not None:
        text_style["strikethrough"] = strikethrough
        fields.append("strikethrough")
    if font_family is not None:
        text_style["weightedFontFamily"] = {"fontFamily": font_family}
        fields.append("weightedFontFamily")
    if font_size is not None:
        text_style["fontSize"] = {"magnitude": font_size, "unit": "PT"}
        fields.append("fontSize")
    if foreground_color is not None:
        text_style["foregroundColor"] = {"color": {"rgbColor": _hex_to_color(foreground_color)}}
        fields.append("foregroundColor")
    if background_color is not None:
        text_style["backgroundColor"] = {"color": {"rgbColor": _hex_to_color(background_color)}}
        fields.append("backgroundColor")

    if not fields:
        raise McpError(ErrorData(code=INVALID_PARAMS, message="Provide at least one text style argument"))

    requests = [
        {
            "updateTextStyle": {
                "range": {"startIndex": s, "endIndex": e},
                "textStyle": text_style,
                "fields": ",".join(fields),
            }
        }
        for s, e in ranges
    ]
    svc.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
    return f"Formatted text in {document_id}"


@google_drive.tool()
async def format_doc_paragraph(
    document_id: str,
    text_to_find: str | None = None,
    occurrence_index: int | None = None,
    start_index: int | None = None,
    end_index: int | None = None,
    alignment: str | None = None,
    heading_style: str | None = None,
    indent_start: float | None = None,
    indent_end: float | None = None,
    line_spacing: float | None = None,
    space_above: float | None = None,
    space_below: float | None = None,
) -> str:
    """Apply paragraph formatting in a Google Doc."""
    token = _get_token()
    svc = _docs_service(token)

    if text_to_find is not None:
        doc = svc.documents().get(documentId=document_id).execute()
        content = doc.get("body", {}).get("content", [])
        ranges = _find_text_ranges(content, text_to_find, occurrence_index)
    elif start_index is not None and end_index is not None:
        ranges = [(start_index, end_index)]
    else:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message="Provide text_to_find or start_index+end_index")
        )

    para_style: dict = {}
    fields: list[str] = []
    if alignment is not None:
        para_style["alignment"] = alignment
        fields.append("alignment")
    if heading_style is not None:
        para_style["namedStyleType"] = heading_style
        fields.append("namedStyleType")
    if indent_start is not None:
        para_style["indentStart"] = {"magnitude": indent_start, "unit": "PT"}
        fields.append("indentStart")
    if indent_end is not None:
        para_style["indentEnd"] = {"magnitude": indent_end, "unit": "PT"}
        fields.append("indentEnd")
    if line_spacing is not None:
        para_style["lineSpacing"] = line_spacing
        fields.append("lineSpacing")
    if space_above is not None:
        para_style["spaceAbove"] = {"magnitude": space_above, "unit": "PT"}
        fields.append("spaceAbove")
    if space_below is not None:
        para_style["spaceBelow"] = {"magnitude": space_below, "unit": "PT"}
        fields.append("spaceBelow")

    if not fields:
        raise McpError(ErrorData(code=INVALID_PARAMS, message="Provide at least one paragraph format argument"))

    requests = [
        {
            "updateParagraphStyle": {
                "range": {"startIndex": s, "endIndex": e},
                "paragraphStyle": para_style,
                "fields": ",".join(fields),
            }
        }
        for s, e in ranges
    ]
    svc.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
    return f"Formatted paragraph in {document_id}"


@google_drive.tool()
async def insert_text(
    document_id: str,
    index: int,
    text: str,
) -> str:
    """Insert text at a specific index in a Google Doc."""
    token = _get_token()
    svc = _docs_service(token)
    svc.documents().batchUpdate(
        documentId=document_id,
        body={"requests": [{"insertText": {"location": {"index": index}, "text": text}}]},
    ).execute()
    return f"Inserted text at index {index}"


@google_drive.tool()
async def delete_range(
    document_id: str,
    start_index: int,
    end_index: int,
) -> str:
    """Delete a range of content in a Google Doc."""
    token = _get_token()
    svc = _docs_service(token)
    svc.documents().batchUpdate(
        documentId=document_id,
        body={"requests": [{"deleteContentRange": {
            "range": {"startIndex": start_index, "endIndex": end_index},
        }}]},
    ).execute()
    return f"Deleted range {start_index}:{end_index}"


@google_drive.tool()
async def find_and_replace(
    document_id: str,
    find: str,
    replace: str,
    match_case: bool = False,
) -> str:
    """Find and replace text across a Google Doc."""
    token = _get_token()
    svc = _docs_service(token)
    svc.documents().batchUpdate(
        documentId=document_id,
        body={"requests": [{"replaceAllText": {
            "containsText": {"text": find, "matchCase": match_case},
            "replaceText": replace,
        }}]},
    ).execute()
    return f"Replaced '{find}' with '{replace}'"


@google_drive.tool()
async def insert_table(
    document_id: str,
    index: int,
    rows: int,
    columns: int,
) -> str:
    """Insert a table at a specific index in a Google Doc."""
    token = _get_token()
    svc = _docs_service(token)
    svc.documents().batchUpdate(
        documentId=document_id,
        body={"requests": [{"insertTable": {
            "rows": rows,
            "columns": columns,
            "location": {"index": index},
        }}]},
    ).execute()
    return f"Inserted {rows}x{columns} table at index {index}"


@google_drive.tool()
async def edit_table_cell(
    document_id: str,
    table_index: int,
    row: int,
    column: int,
    text: str,
) -> str:
    """Edit the text in a table cell by table ordinal (0-based), row, and column."""
    token = _get_token()
    svc = _docs_service(token)
    doc = svc.documents().get(documentId=document_id).execute()
    content = doc.get("body", {}).get("content", [])
    table_element = _find_table_by_index(content, table_index)
    table = table_element["table"]
    table_rows = table.get("tableRows", [])
    if row < 0 or row >= len(table_rows):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"Row {row} out of range (table has {len(table_rows)} rows)",
            )
        )
    table_cells = table_rows[row].get("tableCells", [])
    if column < 0 or column >= len(table_cells):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"Column {column} out of range (row has {len(table_cells)} columns)",
            )
        )
    cell_content = table_cells[column].get("content", [])
    cell_start = cell_content[0]["startIndex"]
    cell_end = cell_content[-1]["endIndex"] - 1  # preserve trailing paragraph mark

    requests = []
    if cell_end > cell_start:
        requests.append({"deleteContentRange": {
            "range": {"startIndex": cell_start, "endIndex": cell_end},
        }})
    requests.append({"insertText": {
        "location": {"index": cell_start},
        "text": text,
    }})
    svc.documents().batchUpdate(
        documentId=document_id,
        body={"requests": requests},
    ).execute()
    return f"Edited table cell [{row},{column}]"


@google_drive.tool()
async def create_paragraph_bullets(
    document_id: str,
    text_to_find: str,
    bullet_type: str = "BULLET",
    occurrence_index: int | None = None,
) -> str:
    """Apply bullet list formatting to a paragraph in a Google Doc."""
    _BULLET_MAP = {
        "BULLET": "BULLET_DISC_CIRCLE_SQUARE",
        "DECIMAL": "NUMBERED_DECIMAL_NESTED",
        "ALPHA": "NUMBERED_UPPERALPHA_ALPHA_ROMAN",
    }
    token = _get_token()
    svc = _docs_service(token)
    doc = svc.documents().get(documentId=document_id).execute()
    content = doc.get("body", {}).get("content", [])
    ranges = _find_text_ranges(content, text_to_find, occurrence_index)
    bullet_preset = _BULLET_MAP.get(bullet_type, bullet_type)
    requests = [
        {
            "createParagraphBullets": {
                "range": {"startIndex": s, "endIndex": e},
                "bulletPreset": bullet_preset,
            }
        }
        for s, e in ranges
    ]
    svc.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
    return f"Applied {bullet_type} bullets"


@google_drive.tool()
async def insert_image(
    document_id: str,
    index: int,
    url: str,
    width: float | None = None,
    height: float | None = None,
) -> str:
    """Insert an inline image from a public URL at a specific index in a Google Doc."""
    token = _get_token()
    svc = _docs_service(token)
    inline_image: dict = {"uri": url, "location": {"index": index}}
    if width is not None and height is not None:
        inline_image["objectSize"] = {
            "width": {"magnitude": width, "unit": "PT"},
            "height": {"magnitude": height, "unit": "PT"},
        }
    svc.documents().batchUpdate(
        documentId=document_id,
        body={"requests": [{"insertInlineImage": inline_image}]},
    ).execute()
    return f"Inserted image at index {index}"
