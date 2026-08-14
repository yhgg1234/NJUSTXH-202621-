"""Read task 2.1 Excel output without changing its business semantics."""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd


RENAME_MAPPING = {
    "job_title": "job_title_raw",
    "company": "company_raw",
    "industry": "industry_raw",
    "city": "city_raw",
    "job_level": "job_level_raw",
}

JSON_COLUMNS = (
    "extracted_entities_json",
    "extracted_relations_json",
    "extracted_events_json",
    "quality_issues_json",
)

REQUIRED_RAW_FIELDS = (
    "source_platform",
    "url",
    "published_at",
    "crawled_at",
    "experience",
    "education",
    "job_title_raw",
    "company_raw",
    "industry_raw",
    "city_raw",
    "job_level_raw",
)


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple, set)):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _json_value(value: Any) -> Any:
    """Convert pandas/numpy/date values into JSON-serializable Python values."""

    if _missing(value):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value


def _parse_json_array(value: Any) -> tuple[list[Any], bool]:
    if isinstance(value, list):
        return value, False
    if _missing(value):
        return [], False
    try:
        parsed = json.loads(str(value))
    except (json.JSONDecodeError, TypeError, ValueError):
        return [], True
    return (parsed, False) if isinstance(parsed, list) else ([], True)


def parse_extracted_data(file_path: str | Path) -> list[dict[str, Any]]:
    """Load the 2.1 workbook and deserialize its structured JSON columns.

    The returned records retain every source column. Canonical ``*_raw`` aliases
    are added for downstream task 2.2 processing. Invalid JSON cells are kept as
    empty arrays and recorded in ``_parse_issues`` for the quality report.
    """

    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"未找到数据文件: {path}")

    dataframe = pd.read_excel(path)

    # Keep the teammate's established precedence: when both old and canonical
    # names exist, the old source column is renamed over the canonical column.
    for origin, target in RENAME_MAPPING.items():
        if origin in dataframe.columns and target in dataframe.columns:
            dataframe = dataframe.drop(columns=[target])
    dataframe = dataframe.rename(
        columns={origin: target for origin, target in RENAME_MAPPING.items() if origin in dataframe.columns}
    )

    records: list[dict[str, Any]] = []
    for source_row, (_, row) in enumerate(dataframe.iterrows(), start=2):
        record = {key: _json_value(value) for key, value in row.to_dict().items()}
        parse_issues: list[str] = []

        for column in JSON_COLUMNS:
            parsed, invalid = _parse_json_array(record.get(column))
            record[column] = parsed
            if invalid:
                parse_issues.append(f"invalid_json:{column}")

        if _missing(record.get("raw_text")):
            responsibilities = "" if _missing(record.get("responsibilities")) else str(record["responsibilities"])
            requirements = "" if _missing(record.get("requirements")) else str(record["requirements"])
            record["raw_text"] = f"{responsibilities}\n{requirements}".strip()

        for field in REQUIRED_RAW_FIELDS:
            if _missing(record.get(field)):
                record[field] = None if field in {"published_at", "crawled_at"} else ""

        record["_source_row"] = source_row
        record["_parse_issues"] = parse_issues
        records.append(record)

    return records
