from django.db import models

from apps.core.mixinx import EncryptMixin
from apps.core.models.maintainer_info import MaintainerInfo
from apps.core.models.time_info import TimeInfo


class ConnectionCredential(MaintainerInfo, TimeInfo, EncryptMixin):
    """系统管理持有的连接凭据。密钥只存在 payload 中，任务侧只引用 id。"""

    name = models.CharField(max_length=128)
    credential_type = models.CharField(max_length=64, db_index=True)
    username = models.CharField(max_length=256, blank=True, default="")
    payload = models.JSONField(default=dict)
    team = models.JSONField(default=list)

    class Meta:
        verbose_name = "连接凭据"
        verbose_name_plural = verbose_name
        ordering = ("-id",)
