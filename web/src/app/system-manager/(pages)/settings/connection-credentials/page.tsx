'use client';

import React, { useEffect, useState } from 'react';
import { Button, Form, Input, Popconfirm, Space, message } from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons';
import Cookies from 'js-cookie';
import CustomTable from '@/components/custom-table';
import PermissionWrapper from '@/components/permission';
import TopSection from '@/components/top-section';
import { useTranslation } from '@/utils/i18n';
import { useLocalizedTime } from '@/hooks/useLocalizedTime';
import {
  CONNECTION_CREDENTIAL_SECRET_MASK,
  type ConnectionCredentialListItem,
  useConnectionCredentialApi,
} from '@/app/system-manager/api/connection-credential';
import ConnectionCredentialFormModal, {
  type ConnectionCredentialFormValues,
} from '@/app/system-manager/components/connection-credential-form-modal';
import {
  listRowHasSecretMaterial,
  toConnectionCredentialListRow,
} from '@/app/system-manager/utils/connectionCredentialList';

const DEFAULT_PAGE_SIZE = 10;

const ConnectionCredentialPage: React.FC = () => {
  const { t } = useTranslation();
  const { convertToLocalizedTime } = useLocalizedTime();
  const {
    fetchConnectionCredentials,
    getConnectionCredential,
    createConnectionCredential,
    updateConnectionCredential,
    deleteConnectionCredential,
  } = useConnectionCredentialApi();
  const [form] = Form.useForm<ConnectionCredentialFormValues>();
  const [dataSource, setDataSource] = useState<ConnectionCredentialListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: DEFAULT_PAGE_SIZE, total: 0 });
  const [keyword, setKeyword] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchData = async (page = pagination.current, pageSize = pagination.pageSize, search = keyword) => {
    setLoading(true);
    try {
      const response = await fetchConnectionCredentials(page, pageSize, search);
      const items = (response.items || [])
        .map((item) => toConnectionCredentialListRow(item))
        .filter((item) => !listRowHasSecretMaterial(item as unknown as Record<string, unknown>));
      setDataSource(items);
      setPagination({ current: page, pageSize, total: response.count || 0 });
    } catch {
      message.error(t('common.fetchFailed'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchData(1, DEFAULT_PAGE_SIZE, '');
  }, []);

  const currentTeam = () => {
    const raw = Cookies.get('current_team');
    const teamId = Number(raw);
    return Number.isFinite(teamId) && teamId > 0 ? [teamId] : [];
  };

  const openCreate = () => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({
      credential_type: 'host',
      team: currentTeam(),
    });
    setModalOpen(true);
  };

  const openEdit = async (record: ConnectionCredentialListItem) => {
    try {
      const detail = await getConnectionCredential(record.id);
      const payload = detail.payload || {};
      setEditingId(record.id);
      form.setFieldsValue({
        name: detail.name,
        credential_type: detail.credential_type,
        team: detail.team || currentTeam(),
        username: typeof payload.username === 'string' ? payload.username : detail.username,
        password: typeof payload.password === 'string' ? payload.password : undefined,
        community: typeof payload.community === 'string' ? payload.community : undefined,
        token: typeof payload.token === 'string' ? payload.token : undefined,
        port: typeof payload.port === 'number' ? payload.port : undefined,
      });
      setModalOpen(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('common.fetchFailed'));
    }
  };

  const buildWritePayload = (values: ConnectionCredentialFormValues) => {
    const payload: Record<string, unknown> = {};
    if (values.username) {
      payload.username = values.username;
    }
    if (values.port) {
      payload.port = values.port;
    }
    if (values.credential_type === 'snmp') {
      payload.community = values.community || (editingId ? CONNECTION_CREDENTIAL_SECRET_MASK : '');
    } else if (values.credential_type === 'influxdb') {
      payload.token = values.token || (editingId ? CONNECTION_CREDENTIAL_SECRET_MASK : '');
    } else {
      payload.password = values.password || (editingId ? CONNECTION_CREDENTIAL_SECRET_MASK : '');
    }
    return {
      name: values.name,
      credential_type: values.credential_type,
      team: values.team,
      payload,
    };
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const body = buildWritePayload(values);
      if (editingId) {
        await updateConnectionCredential(editingId, body);
      } else {
        await createConnectionCredential(body);
      }
      message.success(t('common.updateSuccess'));
      setModalOpen(false);
      await fetchData(editingId ? pagination.current : 1, pagination.pageSize);
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('common.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteConnectionCredential(id);
      const targetPage = dataSource.length === 1 && pagination.current > 1 ? pagination.current - 1 : pagination.current;
      await fetchData(targetPage, pagination.pageSize);
      message.success(t('common.delSuccess'));
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('common.delFailed'));
    }
  };

  const columns = [
    {
      title: t('system.settings.connectionCredential.name'),
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: t('system.settings.connectionCredential.type'),
      dataIndex: 'credential_type',
      key: 'credential_type',
      width: 140,
      render: (value: string) => t(`system.settings.connectionCredential.types.${value}`, value),
    },
    {
      title: t('common.username'),
      dataIndex: 'username',
      key: 'username',
      width: 160,
      ellipsis: true,
      render: (value: string) => value || '-',
    },
    {
      title: t('system.settings.connectionCredential.updatedAt'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (text: string) => (text ? convertToLocalizedTime(text) : '-'),
    },
    {
      title: '',
      key: 'action',
      width: 100,
      render: (_: unknown, record: ConnectionCredentialListItem) => (
        <Space size={0}>
          <PermissionWrapper requiredPermissions={['Edit']}>
            <Button type="text" icon={<EditOutlined />} onClick={() => void openEdit(record)} />
          </PermissionWrapper>
          <PermissionWrapper requiredPermissions={['Delete']}>
            <Popconfirm
              title={t('system.settings.connectionCredential.deleteConfirm')}
              onConfirm={() => handleDelete(record.id)}
              okText={t('common.yes')}
              cancelText={t('common.no')}
            >
              <Button type="text" icon={<DeleteOutlined />} danger />
            </Popconfirm>
          </PermissionWrapper>
        </Space>
      ),
    },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="mb-4 shrink-0">
        <TopSection
          title={t('system.settings.connectionCredential.title')}
          content={t('system.settings.connectionCredential.content')}
        />
      </div>
      <section className="flex min-h-0 flex-1 flex-col rounded-md bg-(--color-bg) p-4">
        <div className="mb-4 flex shrink-0 items-center justify-between gap-3">
          <Input.Search
            allowClear
            className="max-w-xs"
            placeholder={t('system.settings.connectionCredential.searchPlaceholder')}
            onSearch={(value) => {
              setKeyword(value);
              void fetchData(1, pagination.pageSize, value);
            }}
          />
          <PermissionWrapper requiredPermissions={['Add']}>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              {t('system.settings.connectionCredential.add')}
            </Button>
          </PermissionWrapper>
        </div>
        <div className="min-h-0 flex-1">
          <CustomTable<ConnectionCredentialListItem>
            dataSource={dataSource}
            columns={columns}
            loading={loading}
            pagination={{
              current: pagination.current,
              pageSize: pagination.pageSize,
              total: pagination.total,
              showSizeChanger: true,
              onChange: (page, pageSize) => {
                const targetPage = pageSize === pagination.pageSize ? page : 1;
                void fetchData(targetPage, pageSize);
              },
            }}
            rowKey="id"
          />
        </div>
      </section>
      <ConnectionCredentialFormModal
        open={modalOpen}
        editing={editingId !== null}
        form={form}
        saving={saving}
        onSubmit={handleSave}
        onCancel={() => setModalOpen(false)}
      />
    </div>
  );
};

export default ConnectionCredentialPage;
