import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.core.i18n import fallback_summary
from app.models import database
from app.models.schemas import AnalysisRequest, GeneratedAnalysis
from app.services import (
    chart_service,
    comprehensive_analysis_service,
    file_service,
    llm_service,
    markdown_report_service,
)
from app.services.execution_service import ExecutionResult, execute_safe_code
from app.services.preprocess_service import schema_for_dataframe

MAX_ANALYSIS_CODE_ATTEMPTS = 2
RETRYABLE_ANALYSIS_ERROR_CODES = {
    "CODE_UNSAFE",
    "EXECUTION_FAILED",
    "EXECUTION_TIMEOUT",
    "LLM_OUTPUT_INVALID",
}


def submit_analysis(payload: AnalysisRequest) -> dict[str, Any]:
    dataset = file_service.get_dataset(payload.dataset_id)
    df = file_service.load_dataset_dataframe(payload.dataset_id)
    schema = schema_for_dataframe(payload.dataset_id, df)
    selected_model = get_settings().resolve_llm_model(payload.options.model_id)

    generated, execution = _generate_and_execute_analysis(
        df=df,
        schema=schema,
        question=payload.question,
        language=payload.options.language,
        model_id=selected_model.id,
    )
    chart_spec = {**generated.chart_spec.model_dump(), **execution.chart_spec}
    if chart_spec.get("chart_type") in (None, "auto") and generated.chart_type != "auto":
        chart_spec["chart_type"] = generated.chart_type

    chart = chart_service.create_chart(
        dataset_id=payload.dataset_id,
        result_table=execution.table_result,
        chart_spec=chart_spec,
        original_df=df,
    )
    comprehensive = comprehensive_analysis_service.build_comprehensive_analysis(
        dataset_id=payload.dataset_id,
        df=df,
        question=payload.question,
    )
    try:
        question_specific_summary = llm_service.explain_result(
            question=payload.question,
            language=payload.options.language,
            table_result=execution.table_result,
            chart_spec=chart_spec,
            generated=generated,
            model_id=selected_model.id,
        )
    except Exception:
        question_specific_summary = fallback_summary(
            payload.options.language,
            payload.question,
            len(execution.table_result),
            bool(chart.get("chart_url")),
        )
    text_result = comprehensive_analysis_service.executive_summary(comprehensive)
    if question_specific_summary:
        text_result = f"{text_result}\n\nQuestion-specific result: {question_specific_summary}"

    analysis_id = f"an_{uuid4().hex}"
    history_id = f"hist_{uuid4().hex}"
    created_time = datetime.now(timezone.utc).isoformat()
    charts = []
    if chart.get("chart_url"):
        charts.append(
            {
                "name": "question_chart",
                "title": chart_spec.get("title") or "Question Chart",
                "chart_type": chart_spec.get("chart_type") or "auto",
                "chart_id": chart.get("chart_id"),
                "chart_path": chart.get("chart_path"),
                "chart_url": chart.get("chart_url"),
            }
        )
    charts.extend(comprehensive.get("charts", []))
    plan = {
        "model_id": selected_model.id,
        "model": selected_model.model,
        "provider": selected_model.provider,
        "intent": generated.intent,
        "target_fields": generated.target_fields,
        "filters": generated.filters,
        "chart_type": generated.chart_type,
        "steps": generated.steps,
        "confidence": generated.confidence,
        "execution_time_ms": execution.execution_time_ms,
        "stdout": execution.stdout,
        "charts": charts,
        "comprehensive_analysis": comprehensive,
    }

    database.execute(
        """
        INSERT INTO analysis_history (
            history_id, analysis_id, dataset_id, user_question, generated_code,
            text_result, table_result_json, chart_path, chart_url, plan_json,
            language, created_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            history_id,
            analysis_id,
            payload.dataset_id,
            payload.question,
            generated.code,
            text_result,
            json.dumps(execution.table_result, ensure_ascii=False),
            chart.get("chart_path"),
            chart.get("chart_url"),
            json.dumps(plan, ensure_ascii=False),
            payload.options.language,
            created_time,
        ),
    )

    result = {
        "analysis_id": analysis_id,
        "history_id": history_id,
        "dataset_id": payload.dataset_id,
        "dataset_file_name": dataset["file_name"],
        "model_id": selected_model.id,
        "model": selected_model.model,
        "provider": selected_model.provider,
        "question": payload.question,
        "text_result": text_result,
        "table_result": execution.table_result,
        "chart_url": chart.get("chart_url"),
        "charts": charts,
        "chart_spec": chart_spec,
        "comprehensive_analysis": comprehensive,
        "plan": plan,
        "created_time": created_time,
    }
    result["generated_code"] = generated.code
    result["markdown_result"] = markdown_report_service.render_analysis_markdown(
        {**result, "generated_code": generated.code}
    )
    return result


def _generate_and_execute_analysis(
    df: Any,
    schema: dict[str, Any],
    question: str,
    language: str,
    model_id: str,
) -> tuple[GeneratedAnalysis, ExecutionResult]:
    last_error: AppError | None = None
    last_code: str | None = None
    for attempt in range(MAX_ANALYSIS_CODE_ATTEMPTS):
        retry_feedback = _analysis_retry_feedback(last_error, last_code) if last_error else None
        kwargs: dict[str, Any] = {
            "dataset_schema": schema,
            "question": question,
            "language": language,
            "chart_preference": "auto",
            "model_id": model_id,
        }
        if retry_feedback:
            kwargs["retry_feedback"] = retry_feedback
        try:
            generated = llm_service.generate_analysis_code(**kwargs)
            last_code = generated.code
            execution = execute_safe_code(df, generated.code)
            return generated, execution
        except AppError as exc:
            if exc.code not in RETRYABLE_ANALYSIS_ERROR_CODES or attempt == MAX_ANALYSIS_CODE_ATTEMPTS - 1:
                raise
            last_error = exc

    raise last_error or AppError(
        code="EXECUTION_FAILED",
        message="Generated analysis code failed after retry.",
        status_code=400,
    )


def _analysis_retry_feedback(error: AppError | None, generated_code: str | None) -> dict[str, Any] | None:
    if error is None:
        return None
    return {
        "error_code": error.code,
        "error_message": error.message,
        "previous_code": (generated_code or "")[-2000:],
    }


def get_analysis(analysis_id: str) -> dict[str, Any]:
    row = database.fetch_one(
        """
        SELECT *
        FROM analysis_history
        WHERE analysis_id = ?
        """,
        (analysis_id,),
    )
    if row is None:
        raise NotFoundError(code="ANALYSIS_NOT_FOUND", message="Analysis was not found.")
    return _history_row_to_result(row, include_code=True)


def get_generated_code(analysis_id: str) -> dict[str, Any]:
    row = database.fetch_one(
        "SELECT analysis_id, generated_code FROM analysis_history WHERE analysis_id = ?",
        (analysis_id,),
    )
    if row is None:
        raise NotFoundError(code="ANALYSIS_NOT_FOUND", message="Analysis was not found.")
    return row


def rerun_analysis(analysis_id: str) -> dict[str, Any]:
    previous = get_analysis(analysis_id)
    request = AnalysisRequest(
        dataset_id=previous["dataset_id"],
        question=previous["question"],
        options={
            "language": previous.get("language", "en"),
            "model_id": previous.get("model_id"),
            "include_generated_code": True,
        },
    )
    return submit_analysis(request)


def list_history(dataset_id: str | None = None, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size
    params: tuple[Any, ...]
    where = ""
    if dataset_id:
        where = "WHERE dataset_id = ?"
        params = (dataset_id,)
    else:
        params = ()

    total_row = database.fetch_one(f"SELECT COUNT(*) AS count FROM analysis_history {where}", params)
    rows = database.fetch_all(
        f"""
        SELECT *
        FROM analysis_history
        {where}
        ORDER BY created_time DESC
        LIMIT ? OFFSET ?
        """,
        (*params, page_size, offset),
    )
    return {
        "items": [_history_row_to_result(row, include_code=False) for row in rows],
        "total": int(total_row["count"] if total_row else 0),
        "page": page,
        "page_size": page_size,
    }


def delete_history(history_id: str) -> dict[str, Any]:
    row = database.fetch_one("SELECT * FROM analysis_history WHERE history_id = ?", (history_id,))
    if row is None:
        raise NotFoundError(code="HISTORY_NOT_FOUND", message="History record was not found.")
    reports = database.fetch_all("SELECT report_path FROM reports WHERE history_id = ?", (history_id,))
    for report in reports:
        database.remove_file(report.get("report_path"))
    database.remove_file(row.get("chart_path"))
    for chart_path in _chart_paths_from_plan(database.json_loads(row.get("plan_json"), {})):
        database.remove_file(chart_path)
    database.execute("DELETE FROM analysis_history WHERE history_id = ?", (history_id,))
    return {"deleted": True, "history_id": history_id}


def _history_row_to_result(row: dict[str, Any], include_code: bool) -> dict[str, Any]:
    result = {
        "history_id": row["history_id"],
        "analysis_id": row["analysis_id"],
        "dataset_id": row["dataset_id"],
        "question": row["user_question"],
        "text_result": row["text_result"],
        "table_result": database.json_loads(row.get("table_result_json"), []),
        "chart_url": row.get("chart_url"),
        "plan": database.json_loads(row.get("plan_json"), {}),
        "language": row.get("language", "en"),
        "created_time": row["created_time"],
    }
    result["charts"] = result["plan"].get("charts", [])
    if not result["charts"] and result.get("chart_url"):
        result["charts"] = [{"title": "Analysis Chart", "chart_url": result["chart_url"]}]
    result["comprehensive_analysis"] = result["plan"].get("comprehensive_analysis")
    result["model_id"] = result["plan"].get("model_id")
    result["model"] = result["plan"].get("model")
    result["provider"] = result["plan"].get("provider")
    if include_code:
        result["generated_code"] = row["generated_code"]
        result["markdown_result"] = markdown_report_service.render_analysis_markdown(result)
    return result


def _chart_paths_from_plan(plan: dict[str, Any]) -> list[str]:
    chart_paths = []
    for chart in plan.get("charts", []):
        if isinstance(chart, dict) and chart.get("chart_path"):
            chart_paths.append(chart["chart_path"])
    return chart_paths
