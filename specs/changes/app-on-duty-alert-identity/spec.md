# 应用能值班 · 告警中心身份字段

Status: implementing

本切片是「应用能值班」拆分 PR 的第一片（B）：监控 / 日志推送告警中心时携带
`inst_uuid`、`model`、原始标签和独立标题。不做凭据中心、前端公共组件、CMDB
扫描扩族或运营分析拓扑。

## Problem Statement

告警中心已有 `title` / `description` / `resource_id` / `resource_type` / `labels`
/ `tags`，但监控把标题和正文都写成 `alert.content`，`resource_id` 用监控实例 ID，
不传 `resource_type`；日志标题通常等于正文，且显式留空 `resource_type`。前端
一跳关联条和告警状态组件没有稳定身份可读。

## Solution

- 监控：`resource_id` 始终是 `monitor_instance_id`（未恢复告警指纹，本片不改语义）。
  已关联 CMDB 且 `cmdb_id` 为规范 UUIDv4 时，把 `inst_uuid` 写入 labels / raw_data /
  API；未关联则为空。`model` 按监控对象名映射 CMDB `model_id`（未知对象保持空，
  不回落 host）。`title` 用策略展示名，`description` 用告警正文。
  `original_labels` 来自指标 dimensions，密钥类键丢弃。
- 日志：`title` 用 `policy.alert_name`，`description` 用正文。`inst_uuid` / `model`
  契约键必须在、值可空（日志尚无 CMDB 链接）。能从 `source_id` 解析出的
  `key=value` 作为 `original_labels`。
- 告警中心不新增列。`inst_uuid` 只写入 labels / raw_data / API，不回退 `resource_id`。
  聚合时即使生命周期 labels 不一致，仍回填稳定身份键。不切开、不重开旧未恢复告警。
- Web / OpenAPI 序列化一等暴露 `inst_uuid`、`model`、`original_labels`。

## Out Of Scope

- 系统管理凭据中心与任务改引用 ID
- 前端公共组件注册与挂载
- Redis/Nginx 扫描、应用 run/group、运营分析拓扑
- 日志采集实例与 CMDB 的正式关联

## Compatibility

- `resource_id` 写入路径与 master 相同：始终 `alert.monitor_instance_id`。
- 旧数字图 ID 不得当作 `inst_uuid`。
- 新增顶层键对旧接收端可忽略。
