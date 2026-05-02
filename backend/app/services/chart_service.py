from pathlib import Path
from typing import Any
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from matplotlib.text import Text
import numpy as np
import pandas as pd
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.errors import NotFoundError


CHART_FONT_CANDIDATES = (
    "Hiragino Sans GB",
    "Arial Unicode MS",
    "Heiti TC",
    "Songti SC",
    "Songti TC",
    "PingFang SC",
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "WenQuanYi Micro Hei",
)


def create_chart(
    dataset_id: str,
    result_table: list[dict[str, Any]],
    chart_spec: dict[str, Any],
    original_df: pd.DataFrame,
) -> dict[str, str | None]:
    chart_type = str(chart_spec.get("chart_type") or chart_spec.get("type") or "auto").lower()
    if chart_type == "table":
        return {"chart_id": None, "chart_path": None, "chart_url": None}

    result_df = pd.DataFrame(result_table)
    source_df = result_df if not result_df.empty else original_df
    if source_df.empty:
        return {"chart_id": None, "chart_path": None, "chart_url": None}

    if chart_type == "auto":
        chart_type = _infer_chart_type(source_df)

    font_properties = _configure_chart_fonts()
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=140)
    title = _wrap_title(str(chart_spec.get("title") or f"Analysis result for {dataset_id}"))

    try:
        created = _draw_chart(ax, source_df, chart_type, chart_spec)
        if not created:
            plt.close(fig)
            return {"chart_id": None, "chart_path": None, "chart_url": None}
        ax.set_title(title, fontsize=12, pad=12)
        ax.grid(True, alpha=0.22)
        _apply_font_to_figure(fig, font_properties)
        fig.tight_layout()

        settings = get_settings()
        chart_id = f"chart_{uuid4().hex}"
        chart_path = settings.chart_path / f"{chart_id}.png"
        fig.savefig(chart_path, bbox_inches="tight")
        return {
            "chart_id": chart_id,
            "chart_path": str(chart_path),
            "chart_url": f"/api/charts/{chart_id}",
        }
    finally:
        plt.close(fig)


def _draw_chart(ax, df: pd.DataFrame, chart_type: str, chart_spec: dict[str, Any]) -> bool:
    if chart_type == "heatmap":
        return _draw_heatmap(ax, df)

    x_field, y_field = _resolve_xy_fields(df, chart_spec)
    if not y_field:
        return False

    plot_df = df.copy()
    if x_field and x_field in plot_df.columns:
        plot_df = plot_df[[x_field, y_field]].dropna().head(80).reset_index(drop=True)
    else:
        plot_df = plot_df[[y_field]].dropna().head(80).reset_index(drop=True)
    if plot_df.empty:
        return False

    if chart_type == "pie":
        if not x_field or x_field not in plot_df.columns:
            return False
        pie_df = plot_df.groupby(x_field, dropna=False)[y_field].sum().sort_values(ascending=False).head(12)
        if pie_df.empty:
            return False
        ax.pie(pie_df.values, labels=[str(label) for label in pie_df.index], autopct="%1.1f%%")
        ax.axis("equal")
        return True

    if x_field and x_field in plot_df.columns:
        x_values = plot_df[x_field].astype(str)
    else:
        x_values = np.arange(len(plot_df))

    y_values = pd.to_numeric(plot_df[y_field], errors="coerce")
    valid = y_values.notna()
    if not valid.any():
        return False
    x_values = x_values[valid] if hasattr(x_values, "__getitem__") else x_values
    y_values = y_values[valid]

    if chart_type == "scatter":
        numeric_x = pd.to_numeric(plot_df[x_field], errors="coerce") if x_field in plot_df.columns else pd.Series(np.arange(len(y_values)))
        ax.scatter(numeric_x[valid], y_values, s=36, alpha=0.8)
    elif chart_type == "bar":
        ax.bar(x_values.astype(str), y_values)
        ax.tick_params(axis="x", rotation=35)
    else:
        ax.plot(x_values.astype(str), y_values, marker="o", linewidth=2)
        ax.tick_params(axis="x", rotation=35)

    if x_field:
        ax.set_xlabel(str(chart_spec.get("x_label") or chart_spec.get("xlabel") or x_field))
    ax.set_ylabel(str(chart_spec.get("y_label") or chart_spec.get("ylabel") or y_field))
    return True


def _draw_heatmap(ax, df: pd.DataFrame) -> bool:
    numeric_df = df.select_dtypes(include=[np.number])
    if len(numeric_df.columns) < 2:
        return False
    corr = numeric_df.corr(numeric_only=True)
    image = ax.imshow(corr, cmap="viridis", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr.index)))
    ax.set_yticklabels(corr.index)
    plt.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    return True


def _resolve_xy_fields(df: pd.DataFrame, chart_spec: dict[str, Any]) -> tuple[str | None, str | None]:
    columns = [str(column) for column in df.columns]
    x_field = chart_spec.get("x_field") or chart_spec.get("x")
    y_field = chart_spec.get("y_field") or chart_spec.get("y")
    x_field = str(x_field) if x_field in columns else None
    y_field = str(y_field) if y_field in columns else None

    numeric_columns = [str(column) for column in df.select_dtypes(include=[np.number]).columns]
    if y_field is None:
        y_field = next((column for column in numeric_columns if column != x_field), None)
    if x_field is None:
        x_field = next((column for column in columns if column != y_field), None)
    return x_field, y_field


def _infer_chart_type(df: pd.DataFrame) -> str:
    numeric_count = len(df.select_dtypes(include=[np.number]).columns)
    if numeric_count >= 2:
        return "scatter"
    if len(df) <= 12:
        return "bar"
    return "line"


def _configure_chart_fonts() -> FontProperties | None:
    font_properties = _find_chart_font()
    if font_properties is not None:
        font_name = font_properties.get_name()
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = [
            font_name,
            *[name for name in CHART_FONT_CANDIDATES if name != font_name],
            "DejaVu Sans",
        ]
    plt.rcParams["axes.unicode_minus"] = False
    return font_properties


def _find_chart_font() -> FontProperties | None:
    for font_name in CHART_FONT_CANDIDATES:
        try:
            font_path = font_manager.findfont(font_name, fallback_to_default=False)
        except ValueError:
            continue
        if font_path and Path(font_path).exists():
            return FontProperties(fname=font_path)
    return None


def _apply_font_to_figure(fig, font_properties: FontProperties | None) -> None:
    if font_properties is None:
        return
    for text in fig.findobj(match=Text):
        font_size = text.get_fontsize()
        text.set_fontproperties(font_properties)
        text.set_fontsize(font_size)


def _wrap_title(title: str, max_chars: int = 34) -> str:
    cleaned = " ".join(title.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return "\n".join(cleaned[index : index + max_chars] for index in range(0, len(cleaned), max_chars))


def chart_file_response(chart_id: str, download: bool = False) -> FileResponse:
    settings = get_settings()
    path = _chart_path_from_id(chart_id, settings.chart_path)
    if not path.exists():
        raise NotFoundError(code="CHART_NOT_FOUND", message="Chart was not found.")
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{chart_id}.png"'
    return FileResponse(path=path, media_type="image/png", headers=headers)


def _chart_path_from_id(chart_id: str, chart_dir: Path) -> Path:
    safe_id = Path(chart_id).name
    return chart_dir / f"{safe_id}.png"
