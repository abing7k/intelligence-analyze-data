import os
from pathlib import Path

import pandas as pd
import pytest

os.environ["DATABASE_PATH"] = str(Path(__file__).resolve().parents[1] / "storage" / "test_app.sqlite3")

from app.core.errors import AppError
from app.services.execution_service import execute_safe_code


def test_execute_safe_code_allows_time_import_for_generated_timing_code():
    result = execute_safe_code(
        pd.DataFrame({"value": [1, 2, 3]}),
        "\n".join(
            [
                "import time",
                "started = time.perf_counter()",
                "result_table = [{'total': int(df['value'].sum()), 'elapsed': time.perf_counter() - started}]",
                "chart_spec = {'chart_type': 'table', 'title': 'Total value'}",
            ]
        ),
    )

    assert result.table_result[0]["total"] == 6


def test_execute_safe_code_rejects_time_sleep():
    with pytest.raises(AppError, match="sleep"):
        execute_safe_code(
            pd.DataFrame({"value": [1]}),
            "\n".join(
                [
                    "import time",
                    "time.sleep(1)",
                    "result_table = [{'value': 1}]",
                    "chart_spec = {'chart_type': 'table', 'title': 'Value'}",
                ]
            ),
        )
