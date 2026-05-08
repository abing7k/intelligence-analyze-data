import json
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import HRFlowable


PDF_FONT_NAME = "STSong-Light"
PDF_FALLBACK_FONT_NAME = "NotoSansCJK"
PDF_FONT_PATHS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
)


def render_analysis_markdown(history: dict[str, Any]) -> str:
    lines = [
        "# Analysis Report",
        "",
        "## Question",
        _clean_text(history.get("question") or "-"),
        "",
        "## Summary",
    ]
    lines.extend(_render_text_result_lines(history.get("text_result")))
    lines.append("")

    comprehensive = history.get("comprehensive_analysis") or {}
    if comprehensive:
        lines.extend(_render_comprehensive_report(comprehensive))

    charts = _chart_records(history)
    if charts:
        lines.extend(["## Charts", ""])
        for chart in charts:
            title = _clean_text(chart.get("title") or chart.get("name") or "Analysis chart")
            chart_url = chart.get("chart_url")
            if chart_url:
                lines.extend([f"### {title}", f"![{title}]({chart_url})", ""])

    lines.extend(
        [
            "## Question-Specific Result Table",
            _render_markdown_table(history.get("table_result") or []),
            "",
            "## Plan",
            _render_plan(history.get("plan") or {}),
            "",
            "## Code",
            "```python",
            str(history.get("generated_code") or "# Generated code was not included in this response."),
            "```",
            "",
            "## Metadata",
            _render_metadata(history),
            "",
        ]
    )
    return "\n".join(lines)


def render_markdown_pdf(markdown: str, output_path: Path) -> None:
    render_markdown_pdf_with_images(markdown, output_path, image_paths=[])


def render_markdown_pdf_with_images(markdown: str, output_path: Path, image_paths: list[str]) -> None:
    font_name = _register_pdf_font()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=0.58 * inch,
        rightMargin=0.58 * inch,
        topMargin=0.62 * inch,
        bottomMargin=0.58 * inch,
        title="Analysis Report",
        author="Intelligent Data Analysis System",
    )
    story = _build_pdf_story(markdown, image_paths, font_name, doc.width, doc.height)
    doc.build(story, onFirstPage=_draw_pdf_footer, onLaterPages=_draw_pdf_footer)


def _register_pdf_font() -> str:
    for font_path in PDF_FONT_PATHS:
        path = Path(font_path)
        if not path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(PDF_FALLBACK_FONT_NAME, str(path), subfontIndex=0))
            return PDF_FALLBACK_FONT_NAME
        except TypeError:
            try:
                pdfmetrics.registerFont(TTFont(PDF_FALLBACK_FONT_NAME, str(path)))
                return PDF_FALLBACK_FONT_NAME
            except Exception:
                continue
        except Exception:
            continue
    try:
        pdfmetrics.getFont(PDF_FONT_NAME)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(PDF_FONT_NAME))
    return PDF_FONT_NAME


def _pdf_styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = ParagraphStyle(
        "Body",
        fontName=font_name,
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1f2937"),
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base,
            fontSize=20,
            leading=26,
            textColor=colors.HexColor("#111827"),
            spaceAfter=16,
        ),
        "heading2": ParagraphStyle(
            "Heading2",
            parent=base,
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#111827"),
            spaceBefore=10,
            spaceAfter=8,
        ),
        "heading3": ParagraphStyle(
            "Heading3",
            parent=base,
            fontSize=11.5,
            leading=15,
            textColor=colors.HexColor("#111827"),
            spaceBefore=8,
            spaceAfter=6,
        ),
        "heading4": ParagraphStyle(
            "Heading4",
            parent=base,
            fontSize=10.2,
            leading=13.5,
            textColor=colors.HexColor("#111827"),
            spaceBefore=6,
            spaceAfter=4,
        ),
        "body": base,
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base,
            leftIndent=12,
            firstLineIndent=-8,
            spaceAfter=4,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base,
            fontSize=8,
            leading=10,
            backColor=colors.HexColor("#f8fafc"),
            borderColor=colors.HexColor("#e5e7eb"),
            borderWidth=0.5,
            borderPadding=6,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base,
            fontSize=7.5,
            leading=9.5,
            spaceAfter=0,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base,
            fontSize=7.7,
            leading=9.7,
            textColor=colors.HexColor("#111827"),
            spaceAfter=0,
        ),
    }


def _build_pdf_story(
    markdown: str,
    image_paths: list[str],
    font_name: str,
    available_width: float,
    available_height: float,
) -> list[Any]:
    styles = _pdf_styles(font_name)
    story: list[Any] = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index].rstrip()
        line = raw_line.strip()

        if not line:
            story.append(Spacer(1, 4))
            index += 1
            continue

        if line.startswith("```"):
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index].rstrip())
                index += 1
            if index < len(lines):
                index += 1
            story.append(Preformatted("\n".join(code_lines) or " ", styles["code"], maxLineLength=92))
            continue

        if _is_markdown_table_line(line):
            table_lines: list[str] = []
            while index < len(lines) and _is_markdown_table_line(lines[index].strip()):
                table_lines.append(lines[index].strip())
                index += 1
            table = _markdown_table_to_flowable(table_lines, styles, available_width)
            if table is not None:
                story.append(table)
                story.append(Spacer(1, 8))
            continue

        if _is_markdown_image(line):
            index += 1
            continue

        if _is_markdown_rule(line):
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.45,
                    color=colors.HexColor("#d1d5db"),
                    spaceBefore=6,
                    spaceAfter=8,
                )
            )
        elif line.startswith("# "):
            story.append(Paragraph(_inline_text(line[2:]), styles["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(_inline_text(line[3:]), styles["heading2"]))
        elif line.startswith("### "):
            story.append(Paragraph(_inline_text(line[4:]), styles["heading3"]))
        elif line.startswith("#### "):
            story.append(Paragraph(_inline_text(line[5:]), styles["heading4"]))
        elif line.startswith("##### "):
            story.append(Paragraph(_inline_text(line[6:]), styles["heading4"]))
        elif line.startswith("###### "):
            story.append(Paragraph(_inline_text(line[7:]), styles["heading4"]))
        elif line.startswith("- "):
            story.append(Paragraph(f"• {_inline_text(line[2:])}", styles["bullet"]))
        elif re.match(r"^\d+\.\s+", line):
            story.append(Paragraph(_inline_text(line), styles["bullet"]))
        else:
            story.append(Paragraph(_inline_text(line), styles["body"]))
        index += 1

    existing_image_paths = [Path(path) for path in image_paths if Path(path).exists()]
    if existing_image_paths:
        story.append(PageBreak())
        story.append(Paragraph("Charts", styles["heading2"]))
        for image_path in existing_image_paths:
            image = Image(str(image_path))
            max_width = available_width
            max_height = available_height * 0.62
            scale = min(max_width / image.imageWidth, max_height / image.imageHeight, 1)
            image.drawWidth = image.imageWidth * scale
            image.drawHeight = image.imageHeight * scale
            story.extend([image, Spacer(1, 12)])
    return story


def _markdown_table_to_flowable(
    table_lines: list[str],
    styles: dict[str, ParagraphStyle],
    available_width: float,
) -> Table | None:
    rows = [_split_markdown_table_row(line) for line in table_lines]
    rows = [row for row in rows if row]
    rows = [row for row in rows if not _is_separator_row(row)]
    if not rows:
        return None

    column_count = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (column_count - len(row)) for row in rows]
    col_widths = [available_width / column_count] * column_count
    data = [
        [
            Paragraph(_inline_text(cell), styles["table_header" if row_index == 0 else "table_cell"])
            for cell in row
        ]
        for row_index, row in enumerate(normalized_rows)
    ]
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _draw_pdf_footer(canvas, doc) -> None:
    font_name = _register_pdf_font()
    canvas.saveState()
    canvas.setFont(font_name, 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawRightString(A4[0] - 0.58 * inch, 0.34 * inch, str(canvas.getPageNumber()))
    canvas.restoreState()


def _is_markdown_table_line(line: str) -> bool:
    return line.startswith("|") and line.endswith("|")


def _is_markdown_image(line: str) -> bool:
    return bool(re.match(r"^!\[[^\]]*\]\([^)]+\)$", line))


def _is_markdown_rule(line: str) -> bool:
    return bool(re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", line.strip()))


def _split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for character in stripped:
        if escaped:
            current.append(character)
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(character)
    cells.append("".join(current).strip())
    return cells


def _is_separator_row(row: list[str]) -> bool:
    return bool(row) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in row)


def _inline_text(value: Any) -> str:
    text = _clean_text(value)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = text.replace("_No table result._", "No table result.")
    text = text.replace("_No execution plan._", "No execution plan.")
    text = text.replace("_No metadata._", "No metadata.")
    escaped = xml_escape(text)
    return escaped.replace("&lt;br&gt;", "<br/>").replace("&lt;br/&gt;", "<br/>")


def _render_text_result_lines(value: Any) -> list[str]:
    text = _clean_text(value)
    if not text:
        return ["-"]

    marker = "Question-specific result:"
    if marker not in text:
        return _normalize_embedded_markdown_lines(text)

    summary, question_specific = text.split(marker, 1)
    lines = _normalize_embedded_markdown_lines(summary)
    question_specific = question_specific.strip()
    if question_specific:
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(["## Question-Specific Result", ""])
        lines.extend(_normalize_embedded_markdown_lines(question_specific, heading_offset=2))
    return lines or ["-"]


def _normalize_embedded_markdown_lines(text: str, heading_offset: int = 0) -> list[str]:
    lines: list[str] = []
    for raw_line in text.strip().splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = min(len(heading.group(1)) + heading_offset, 6)
            line = f"{'#' * level} {heading.group(2).strip()}"
        lines.append(line)
    return lines


def chart_image_paths(history: dict[str, Any]) -> list[str]:
    paths = []
    for chart in _chart_records(history):
        path = chart.get("chart_path")
        if path:
            paths.append(str(path))
    return paths


def _render_comprehensive_report(report: dict[str, Any]) -> list[str]:
    profile = report.get("profile") or {}
    quality = report.get("quality") or {}
    predictive = report.get("predictive_model") or {}
    lines = [
        "## Dataset Overview",
        _render_markdown_table([profile]) if profile else "_No dataset profile._",
        "",
        "## Data Quality",
        f"- **Total missing cells:** {quality.get('total_missing_cells', 0)}",
        f"- **Columns with missing values:** {quality.get('columns_with_missing', 0)}",
        "",
        "### Column Quality",
        _render_markdown_table((quality.get("column_quality") or [])[:30]),
        "",
    ]

    numeric_summary = report.get("numeric_summary") or []
    if numeric_summary:
        lines.extend(["## Numeric Summary", _render_markdown_table(numeric_summary[:30]), ""])

    categorical_summary = report.get("categorical_summary") or []
    if categorical_summary:
        lines.extend(["## Categorical Summary", ""])
        for item in categorical_summary[:12]:
            lines.append(f"### {_clean_text(item.get('column'))}")
            top_values = item.get("top_values") or []
            lines.append(_render_markdown_table(top_values))
            lines.append("")

    correlation = report.get("correlation") or {}
    lines.extend(["## Correlation Analysis", ""])
    if correlation.get("status") == "completed":
        lines.extend(
            [
                f"- **Method:** {_clean_text(correlation.get('method', 'pearson'))}",
                "",
                "### Strongest Correlations",
                _render_markdown_table(correlation.get("strongest_pairs") or []),
                "",
            ]
        )
    else:
        lines.extend([f"_Skipped: {_clean_text(correlation.get('reason') or 'Not enough numeric data.')}._", ""])

    outliers = report.get("outliers") or []
    if outliers:
        lines.extend(["## Outlier Check", _render_markdown_table(outliers[:30]), ""])

    lines.extend(["## Predictive Modelling", ""])
    if predictive.get("status") == "completed":
        lines.extend(_render_predictive_model(predictive))
    else:
        lines.extend(
            [
                f"_Skipped: {_clean_text(predictive.get('reason') or 'No suitable modelling target.')}_",
                "",
            ]
        )

    notes = report.get("notes") or []
    if notes:
        lines.extend(["## Method Notes", *[f"- {_clean_text(note)}" for note in notes], ""])
    return lines


def _render_predictive_model(model: dict[str, Any]) -> list[str]:
    lines = [
        f"- **Target:** {_clean_text(model.get('target'))}",
        f"- **Task type:** {_clean_text(model.get('task_type'))}",
        f"- **Target selection:** {_clean_text(model.get('target_reason'))}",
        f"- **Rows used:** {_clean_text(model.get('row_count_used'))}",
        f"- **Feature count:** {_clean_text(model.get('feature_count_used'))}",
        "",
        "### Holdout Metrics",
        _render_key_value_table(model.get("holdout_metrics") or {}),
        "",
        "### Cross Validation",
        _render_key_value_table(model.get("cross_validation") or {}),
        "",
    ]
    if model.get("class_distribution"):
        lines.extend(["### Class Distribution", _render_markdown_table(model["class_distribution"]), ""])
    if model.get("top_features"):
        lines.extend(["### Top Predictive Features", _render_markdown_table(model["top_features"]), ""])
    return lines


def _render_key_value_table(values: dict[str, Any]) -> str:
    rows = [{"metric": key, "value": value} for key, value in values.items()]
    return _render_markdown_table(rows)


def _render_markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No table result._"

    columns = list(rows[0].keys())
    header = "| " + " | ".join(_escape_table_cell(column) for column in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(_escape_table_cell(row.get(column, "")) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def _chart_records(history: dict[str, Any]) -> list[dict[str, Any]]:
    charts = history.get("charts") or []
    if charts:
        return [chart for chart in charts if isinstance(chart, dict)]
    chart_url = history.get("chart_url")
    return [{"title": "Analysis Chart", "chart_url": chart_url}] if chart_url else []


def _render_plan(plan: dict[str, Any]) -> str:
    if not plan:
        return "_No execution plan._"

    lines = []
    for key in ("model_id", "model", "provider", "intent", "chart_type", "execution_time_ms"):
        if key in plan and plan[key] not in (None, ""):
            lines.append(f"- **{_humanize_key(key)}:** {_clean_text(plan[key])}")

    steps = plan.get("steps")
    if isinstance(steps, list) and steps:
        lines.append("- **Steps:**")
        lines.extend(f"  {index}. {_clean_text(step)}" for index, step in enumerate(steps, start=1))

    target_fields = plan.get("target_fields")
    if isinstance(target_fields, list) and target_fields:
        lines.append(f"- **Target fields:** {', '.join(_clean_text(field) for field in target_fields)}")

    filters = plan.get("filters")
    if filters:
        lines.append("- **Filters:**")
        lines.append("```json")
        lines.append(json.dumps(filters, ensure_ascii=False, indent=2))
        lines.append("```")

    return "\n".join(lines) if lines else "```json\n" + json.dumps(plan, ensure_ascii=False, indent=2) + "\n```"


def _render_metadata(history: dict[str, Any]) -> str:
    metadata = {
        "analysis_id": history.get("analysis_id"),
        "history_id": history.get("history_id"),
        "dataset_id": history.get("dataset_id"),
        "dataset_file_name": history.get("dataset_file_name"),
        "language": history.get("language"),
        "created_time": history.get("created_time"),
    }
    lines = [
        f"- **{_humanize_key(key)}:** {_clean_text(value)}"
        for key, value in metadata.items()
        if value not in (None, "")
    ]
    return "\n".join(lines) if lines else "_No metadata._"


def _escape_table_cell(value: Any) -> str:
    return _clean_text(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _humanize_key(value: str) -> str:
    return value.replace("_", " ").capitalize()
