"""查找采集 / 扫描 / 监控对系统管理连接凭据的引用，删除前拦截。"""

import logging

from apps.core.exceptions.base_app_exception import ValidationAppException

KIND_LABELS = {
    "collect": "采集任务",
    "scan": "扫描任务",
    "monitor": "监控实例",
}


class ConnectionCredentialInUseError(ValidationAppException):
    ERROR_CODE = "4004091"
    MESSAGE = "连接凭据仍被任务引用，无法删除"
    STATUS_CODE = 409
    LOG_LEVEL = logging.INFO


def payload_references_store_id(payload, store_id):
    """任务 / 实例 JSON 是否引用该系统管理凭据 ID。"""
    if store_id in (None, ""):
        return False
    expected = str(store_id).strip()
    if not expected.isdigit():
        return False
    return _walk_references(payload, expected)


def _walk_references(payload, expected):
    if isinstance(payload, dict):
        system_id = payload.get("system_credential_id")
        if system_id not in (None, "") and str(system_id).strip() == expected:
            return True
        credential_id = payload.get("credential_id")
        if credential_id not in (None, "") and str(credential_id).strip() == expected:
            return True
        return any(_walk_references(value, expected) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return any(_walk_references(item, expected) for item in payload)
    return False


def find_connection_credential_references(store_id, limit=5):
    """返回仍引用该凭据的任务 / 实例摘要。"""
    expected = str(store_id).strip() if store_id not in (None, "") else ""
    if not expected.isdigit():
        return []

    refs = []
    refs.extend(_collect_task_refs(expected, limit))
    if len(refs) >= limit:
        return refs
    refs.extend(_scan_task_refs(expected, limit - len(refs)))
    if len(refs) >= limit:
        return refs
    refs.extend(_monitor_instance_refs(expected, limit - len(refs)))
    return refs


def assert_connection_credential_unused(store_id):
    refs = find_connection_credential_references(store_id, limit=3)
    if not refs:
        return
    first = refs[0]
    kind = KIND_LABELS.get(first["kind"], first["kind"])
    name = first.get("name") or first.get("id")
    extra = len(refs) - 1
    if extra:
        message = f"连接凭据仍被{kind}「{name}」等 {1 + extra} 处引用，无法删除"
    else:
        message = f"连接凭据仍被{kind}「{name}」引用，无法删除"
    raise ConnectionCredentialInUseError(message)


def _collect_task_refs(expected, limit):
    from apps.cmdb.models.collect_model import CollectModels

    refs = []
    for task in CollectModels.objects.only("id", "name", "credential").iterator():
        if payload_references_store_id(task.credential, expected):
            refs.append({"kind": "collect", "id": task.id, "name": task.name})
            if len(refs) >= limit:
                break
    return refs


def _scan_task_refs(expected, limit):
    from apps.cmdb.models.scan_model import ScanTask

    refs = []
    for task in ScanTask.objects.only("id", "name", "credentials").iterator():
        if payload_references_store_id(task.credentials, expected):
            refs.append({"kind": "scan", "id": task.id, "name": task.name})
            if len(refs) >= limit:
                break
    return refs


def _monitor_instance_refs(expected, limit):
    from apps.monitor.models import MonitorInstance

    refs = []
    queryset = MonitorInstance.objects.filter(is_deleted=False).only("id", "name", "summary_facts")
    for instance in queryset.iterator():
        if payload_references_store_id(instance.summary_facts, expected):
            refs.append({"kind": "monitor", "id": instance.id, "name": instance.name or instance.id})
            if len(refs) >= limit:
                break
    return refs
