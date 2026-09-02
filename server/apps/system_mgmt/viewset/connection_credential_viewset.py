from django_filters import filters
from django_filters.rest_framework import FilterSet
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.core.decorators.api_permission import HasPermission
from apps.core.utils.loader import LanguageLoader
from apps.core.utils.viewset_utils import GenericViewSetFun
from apps.system_mgmt.models.connection_credential import ConnectionCredential
from apps.system_mgmt.serializers.connection_credential_serializer import ConnectionCredentialListSerializer, ConnectionCredentialSerializer
from apps.system_mgmt.utils.group_filter_mixin import filter_queryset_by_group_ids, get_unauthorized_group_ids, get_user_group_ids
from apps.system_mgmt.utils.operation_log_utils import log_operation


class ConnectionCredentialPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200


class ConnectionCredentialFilter(FilterSet):
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")
    credential_type = filters.CharFilter(field_name="credential_type", lookup_expr="exact")


class ConnectionCredentialViewSet(viewsets.ModelViewSet, GenericViewSetFun):
    queryset = ConnectionCredential.objects.all()
    serializer_class = ConnectionCredentialSerializer
    filterset_class = ConnectionCredentialFilter
    pagination_class = ConnectionCredentialPagination
    http_method_names = ["get", "post", "put", "delete", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return ConnectionCredentialListSerializer
        return ConnectionCredentialSerializer

    def _loader(self, request):
        locale = getattr(getattr(request, "user", None), "locale", "en") or "en"
        return LanguageLoader(app="system_mgmt", default_lang=locale)

    def _filter_by_accessible_teams(self, queryset, user):
        user_group_ids = get_user_group_ids(user)
        if user_group_ids is None:
            return queryset
        return filter_queryset_by_group_ids(queryset, user_group_ids, group_field="team")

    def _validate_instance_permission(self, request, instance):
        user_group_ids = get_user_group_ids(request.user)
        if user_group_ids is None:
            return True, None
        instance_team = set()
        for item in instance.team or []:
            try:
                instance_team.add(int(item))
            except (TypeError, ValueError):
                continue
        if user_group_ids and user_group_ids.intersection(instance_team):
            return True, None
        message = self._loader(request).get("error.no_permission_access_team", "无权访问该团队数据")
        return False, Response({"result": False, "message": message}, status=403)

    def _validate_request_team(self, request, *, require_team=False):
        user_group_ids = get_user_group_ids(request.user)
        if user_group_ids is None:
            return True, None
        has_team = "team" in request.data
        if not has_team and not require_team:
            return True, None
        team = request.data.get("team") if has_team else None
        if team in (None, "") and require_team:
            return False, Response({"result": False, "message": "请选择组织"}, status=400)
        unauthorized = get_unauthorized_group_ids(request.user, team or [])
        if unauthorized:
            message = self._loader(request).get("error.no_permission_access_team", "无权访问该团队数据")
            return False, Response({"result": False, "message": message}, status=403)
        return True, None

    def get_queryset(self):
        return self._filter_by_accessible_teams(super().get_queryset(), self.request.user)

    @HasPermission("connection_credential-View")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @HasPermission("connection_credential-View")
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        is_valid, error_response = self._validate_instance_permission(request, obj)
        if not is_valid:
            return error_response
        return super().retrieve(request, *args, **kwargs)

    @HasPermission("connection_credential-Add")
    def create(self, request, *args, **kwargs):
        is_valid, error_response = self._validate_request_team(request, require_team=True)
        if not is_valid:
            return error_response
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            log_operation(request, "create", "system-manager", f"新增连接凭据: {response.data.get('name', '')}")
        return response

    @HasPermission("connection_credential-Edit")
    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        is_valid, error_response = self._validate_instance_permission(request, obj)
        if not is_valid:
            return error_response
        is_valid, error_response = self._validate_request_team(request)
        if not is_valid:
            return error_response
        response = super().update(request, *args, **kwargs)
        if response.status_code == 200:
            log_operation(request, "update", "system-manager", f"编辑连接凭据: {response.data.get('name', obj.name)}")
        return response

    @HasPermission("connection_credential-Delete")
    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        is_valid, error_response = self._validate_instance_permission(request, obj)
        if not is_valid:
            return error_response
        name = obj.name
        response = super().destroy(request, *args, **kwargs)
        if response.status_code == 204:
            log_operation(request, "delete", "system-manager", f"删除连接凭据: {name}")
        return response
