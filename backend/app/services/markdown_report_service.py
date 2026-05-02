import json
import textwrap
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from app.services.chart_service import _find_chart_font


def render_analysis_markdown(history: dict[str, Any]) -> str:
    lines = [
        "# Analysis Report",
        "",
        "## Question",
        _clean_text(history.get("question") or "-"),
        "",
        "## Summary",
        _clean_text(history.get("text_result") or "-"),
        "",
    ]

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
    font_properties = _find_chart_font()
    lines = _wrap_pdf_lines(markdown)
    lines_per_page = 54
    page_chunks = [lines[index : index + lines_per_page] for index in range(0, len(lines), lines_per_page)] or [[]]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(output_path) as pdf:
        for page_index, chunk in enumerate(page_chunks, start=1):
            fig = plt.figure(figsize=(8.27, 11.69), dpi=140)
            fig.patch.set_facecolor("white")
            y = 0.96
            for line in chunk:
                fig.text(
                    0.07,
                    y,
                    line or " ",
                    fontsize=_font_size_for_line(line),
                    fontproperties=font_properties,
                    va="top",
                    color="#111827",
                )
                y -= 0.017
            fig.text(
                0.93,
                0.025,
                str(page_index),
                fontsize=8,
                fontproperties=font_properties,
                ha="right",
                color="#6b7280",
            )
            pdf.savefig(fig)
            plt.close(fig)
        for image_path in image_paths:
            path = Path(image_path)
            if not path.exists():
                continue
            image = plt.imread(path)
            fig, ax = plt.subplots(figsize=(11.69, 8.27), dpi=140)
            ax.imshow(image)
            ax.axis("off")
            fig.tight_layout(pad=0.2)
            pdf.savefig(fig)
            plt.close(fig)


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


def _wrap_pdf_lines(markdown: str) -> list[str]:
    wrapped: list[str] = []
    in_code_block = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            wrapped.append(line)
            continue
        width = 112 if in_code_block or line.startswith("|") else 88
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(line, width=width, replace_whitespace=False) or [""])
    return wrapped


def _font_size_for_line(line: str) -> float:
    if line.startswith("# "):
        return 13
    if line.startswith("## "):
        return 11
    return 8.5


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
