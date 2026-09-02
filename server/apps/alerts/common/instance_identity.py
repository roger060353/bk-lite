"""告警中心实例身份：inst_uuid / model / original_labels。

监控、日志生产者把这三项写入标准 Event 契约；告警中心 API 再从
resource_*、labels、tags、raw_data 回读。不新增表字段，避免本切片迁移。
"""

from __future__ import annotations

from typing import Any

from apps.cmdb.services.instance_identity import optional_inst_uuid

LABEL_INST_UUID = "inst_uuid"
LABEL_MODEL = "model"
LABEL_ORIGINAL_LABELS = "original_labels"

_MAX_ORIGINAL_LABEL_KEYS = 32
_MAX_ORIGINAL_LABEL_VALUE_LEN = 256
_FORBIDDEN_LABEL_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "credential",
    "authorization",
    "private_key",
)


def normalize_model_id(value: object) -> str:
    if value in (None, ""):
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "undefined"}:
        return ""
    return text[:64]


def sanitize_original_labels(value: object) -> dict[str, str]:
    """只保留有界标量标签；密钥类键名直接丢弃。"""
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw in value.items():
        if len(result) >= _MAX_ORIGINAL_LABEL_KEYS:
            break
        name = str(key).strip()
        if not name:
            continue
        lowered = name.lower()
        if any(fragment in lowered for fragment in _FORBIDDEN_LABEL_FRAGMENTS):
            continue
        if raw is None or isinstance(raw, (dict, list, tuple, set)):
            continue
        if isinstance(raw, bool):
            text = "true" if raw else "false"
        elif isinstance(raw, (int, float)):
            text = str(raw)
        else:
            text = str(raw).strip()
        if not text:
            continue
        result[name] = text[:_MAX_ORIGINAL_LABEL_VALUE_LEN]
    return result


def extract_instance_identity(obj: Any) -> dict[str, Any]:
    """从 Event / Alert / 简单对象回读前端公共组件所需的三项身份。"""
    labels = getattr(obj, "labels", None)
    if not isinstance(labels, dict):
        labels = {}
    raw_data = getattr(obj, "raw_data", None)
    if not isinstance(raw_data, dict):
        raw_data = {}
    tags = getattr(obj, "tags", None)
    if not isinstance(tags, dict):
        tags = {}

    inst_uuid = (
        optional_inst_uuid(labels.get(LABEL_INST_UUID))
        or optional_inst_uuid(raw_data.get(LABEL_INST_UUID))
        or optional_inst_uuid(getattr(obj, "resource_id", None))
        or ""
    )
    model = (
        normalize_model_id(labels.get(LABEL_MODEL))
        or normalize_model_id(raw_data.get(LABEL_MODEL))
        or normalize_model_id(getattr(obj, "resource_type", None))
        or ""
    )
    original_labels = (
        sanitize_original_labels(labels.get(LABEL_ORIGINAL_LABELS))
        or sanitize_original_labels(raw_data.get(LABEL_ORIGINAL_LABELS))
        or sanitize_original_labels(tags)
    )
    return {
        LABEL_INST_UUID: inst_uuid,
        LABEL_MODEL: model,
        LABEL_ORIGINAL_LABELS: original_labels,
    }


def merge_stable_identity_labels(events: list[Any], labels: dict[str, Any] | None) -> dict[str, Any]:
    """生命周期元数据可能不一致，但仍要把稳定身份键写回 Alert.labels。"""
    merged = dict(labels or {})
    if not events:
        return merged

    identities = [extract_instance_identity(event) for event in events]
    for key in (LABEL_INST_UUID, LABEL_MODEL):
        values = {item.get(key) for item in identities if item.get(key)}
        if len(values) == 1:
            merged[key] = values.pop()

    original_values = [item.get(LABEL_ORIGINAL_LABELS) for item in identities if item.get(LABEL_ORIGINAL_LABELS)]
    serialized = {tuple(sorted(item.items())) for item in original_values}
    if len(serialized) == 1:
        merged[LABEL_ORIGINAL_LABELS] = dict(original_values[0])
    return merged
