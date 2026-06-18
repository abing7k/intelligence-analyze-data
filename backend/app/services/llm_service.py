import json
import re
from typing import Any

from app.core.config import LLMModelConfig, get_settings
from app.core.errors import AppError
from app.core.i18n import answer_language_instruction
from app.models.schemas import GeneratedAnalysis


def validate_model(model_id: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    model_chain = settings.resolve_llm_model_chain(model_id)
    errors: list[str] = []
    for index, model_config in enumerate(model_chain):
        if not model_config.api_key_value:
            errors.append(f"{model_config.provider}: API key is not configured.")
            continue
        try:
            if model_config.api_style == "responses":
                _probe_responses(model_config)
            else:
                _probe_model_call(model_config)
            return {
                "model_id": model_config.model,
                "provider": model_config.provider,
                "model": model_config.model,
                "available": True,
                "fallback_enabled": len(model_chain) > 1,
                "active_provider": model_config.provider,
                "provider_priority": [candidate.provider for candidate in model_chain],
                "message": (
                    "Model is available."
                    if index == 0
                    else f"Primary provider failed; using fallback provider '{model_config.provider}'."
                ),
            }
        except Exception as exc:
            errors.append(f"{model_config.provider}: {_safe_error_message(exc)}")

    selected = model_chain[0]
    return {
        "model_id": selected.model,
        "provider": selected.provider,
        "model": selected.model,
        "available": False,
        "fallback_enabled": len(model_chain) > 1,
        "provider_priority": [candidate.provider for candidate in model_chain],
        "message": "All configured providers failed: " + " | ".join(errors[-3:]),
    }


def generate_analysis_code(
    dataset_schema: dict[str, Any],
    question: str,
    language: str,
    chart_preference: str = "auto",
    model_id: str | None = None,
) -> GeneratedAnalysis:
    system_prompt = (
        "You are a LangChain-orchestrated senior data analyst. Generate safe Python pandas code "
        "for an uploaded tabular dataset. The code will run in a restricted environment where "
        "df, pd, and np already exist. If imports are necessary, only import pandas, numpy, "
        "math, statistics, or time; do not use time.sleep. Do not read or write files. "
        "Do not use network, OS, subprocess, pathlib, requests, eval, exec, open, "
        "or hidden/private attributes. "
        "The code must assign result_table and chart_spec. result_table should be a pandas "
        "DataFrame, Series, list of dicts, or dict. chart_spec must be a dict with chart_type, "
        "x_field, y_field, and title when a chart is useful. chart_spec.title must be a complete, "
        "human-readable chart title in the requested answer language, not a placeholder and not empty. "
        "If axis labels would be clearer than raw column names, include optional x_label and y_label "
        "in chart_spec while keeping x_field and y_field exactly equal to real result_table columns. "
        f"{answer_language_instruction(language)} Return only valid JSON."
    )
    user_prompt = json.dumps(
        {
            "dataset_schema": dataset_schema,
            "question": question,
            "preferred_chart_type": chart_preference,
            "required_json_schema": {
                "intent": "short intent name",
                "target_fields": ["field names used"],
                "filters": [{"field": "field", "operator": "=", "value": "value"}],
                "chart_type": "auto|line|bar|pie|scatter|heatmap|table",
                "steps": ["step 1", "step 2"],
                "code": "Python code that assigns result_table and chart_spec",
                "chart_spec": {
                    "chart_type": "line|bar|pie|scatter|heatmap|table",
                    "x_field": "column or null",
                    "y_field": "column or null",
                    "group_field": "column or null",
                    "title": "chart title",
                    "x_label": "readable x-axis label or null",
                    "y_label": "readable y-axis label or null",
                },
                "confidence": 0.0,
            },
        },
        ensure_ascii=False,
    )
    content = _invoke_model(system_prompt, user_prompt, json_mode=True, model_id=model_id)
    payload = _parse_json_object(content)
    if chart_preference != "auto":
        payload["chart_type"] = chart_preference
        payload.setdefault("chart_spec", {})["chart_type"] = chart_preference
    try:
        return GeneratedAnalysis.model_validate(payload)
    except Exception as exc:
        raise AppError(
            code="LLM_OUTPUT_INVALID",
            message=f"Model output did not match the expected analysis schema: {exc}",
            status_code=502,
        ) from exc


def explain_result(
    question: str,
    language: str,
    table_result: list[dict[str, Any]],
    chart_spec: dict[str, Any],
    generated: GeneratedAnalysis,
    model_id: str | None = None,
) -> str:
    system_prompt = (
        "You explain data analysis results for non-programmers. Be concise and specific. "
        "Mention important trends, comparisons, limitations, and what the chart shows. "
        f"{answer_language_instruction(language)}"
    )
    user_prompt = json.dumps(
        {
            "question": question,
            "analysis_intent": generated.intent,
            "analysis_steps": generated.steps,
            "table_result_preview": table_result[:30],
            "chart_spec": chart_spec,
        },
        ensure_ascii=False,
    )
    return _invoke_model(system_prompt, user_prompt, json_mode=False, model_id=model_id).strip()


def _invoke_model(system_prompt: str, user_prompt: str, json_mode: bool, model_id: str | None = None) -> str:
    model_chain = get_settings().resolve_llm_model_chain(model_id)
    errors: list[str] = []
    for model_config in model_chain:
        if not model_config.api_key_value:
            errors.append(f"{model_config.provider}: API key is not configured.")
            continue
        for invoker in _invoker_order(model_config):
            try:
                return invoker(system_prompt, user_prompt, json_mode, model_config)
            except Exception as exc:
                errors.append(f"{model_config.provider}: {_safe_error_message(exc)}")

    raise AppError(
        code="MODEL_UNAVAILABLE",
        message=(
            f"Model '{model_chain[0].model}' failed for all configured providers: "
            f"{' | '.join(errors[-3:])}"
        ),
        status_code=503,
    )


def _invoker_order(model_config: LLMModelConfig):
    if model_config.api_style == "responses":
        return (_invoke_openai_responses,)
    if model_config.api_style == "chat":
        return (_invoke_langchain_chat, _invoke_openai_chat)
    return (_invoke_openai_responses, _invoke_langchain_chat, _invoke_openai_chat)


def _invoke_langchain_chat(
    system_prompt: str,
    user_prompt: str,
    json_mode: bool,
    model_config: LLMModelConfig,
) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    model_kwargs: dict[str, Any] = {}
    if json_mode:
        model_kwargs["response_format"] = {"type": "json_object"}

    llm = ChatOpenAI(
        model=model_config.model,
        api_key=model_config.api_key_value,
        base_url=model_config.normalized_base_url,
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
        model_kwargs=model_kwargs,
    )
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    content = getattr(response, "content", "")
    if isinstance(content, list):
        return "\n".join(str(item) for item in content)
    return str(content)


def _invoke_openai_chat(
    system_prompt: str,
    user_prompt: str,
    json_mode: bool,
    model_config: LLMModelConfig,
) -> str:
    client = _openai_client(model_config)
    kwargs: dict[str, Any] = {
        "model": model_config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception:
        if "response_format" not in kwargs:
            raise
        kwargs.pop("response_format", None)
        response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def _invoke_openai_responses(
    system_prompt: str,
    user_prompt: str,
    json_mode: bool,
    model_config: LLMModelConfig,
) -> str:
    client = _openai_client(model_config)
    text_format: dict[str, Any] | None = None
    if json_mode:
        text_format = {"format": {"type": "json_object"}}
    kwargs: dict[str, Any] = {
        "model": model_config.model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if text_format:
        kwargs["text"] = text_format
    try:
        response = client.responses.create(**kwargs)
    except Exception:
        if "text" not in kwargs:
            raise
        kwargs.pop("text", None)
        response = client.responses.create(**kwargs)
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text
    return str(response)


def _openai_client(model_config: LLMModelConfig):
    from openai import OpenAI

    settings = get_settings()
    return OpenAI(
        api_key=model_config.api_key_value,
        base_url=model_config.normalized_base_url,
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )


def _probe_model_call(model_config: LLMModelConfig) -> None:
    if model_config.api_style == "chat":
        _probe_chat(model_config)
        return
    errors: list[str] = []
    for probe in (_probe_responses, _probe_chat):
        try:
            probe(model_config)
            return
        except Exception as exc:
            errors.append(_safe_error_message(exc))
    raise RuntimeError(" | ".join(errors[-2:]))


def _probe_responses(model_config: LLMModelConfig) -> None:
    client = _openai_client(model_config)
    client.responses.create(
        model=model_config.model,
        input="Reply with only OK.",
        max_output_tokens=16,
    )


def _probe_chat(model_config: LLMModelConfig) -> None:
    client = _openai_client(model_config)
    client.chat.completions.create(
        model=model_config.model,
        messages=[{"role": "user", "content": "Reply with only OK."}],
        max_tokens=8,
    )


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AppError(code="LLM_OUTPUT_INVALID", message="Model did not return valid JSON.", status_code=502)
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise AppError(code="LLM_OUTPUT_INVALID", message="Model JSON output must be an object.", status_code=502)
    return parsed


def _safe_error_message(exc: Exception) -> str:
    settings = get_settings()
    message = str(exc)
    api_keys = [settings.openai_api_key] + [model.api_key_value for model in settings.llm_models]
    for api_key in api_keys:
        if not api_key:
            continue
        message = message.replace(api_key, "***")
    return message[:1000]
