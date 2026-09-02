'use client';

import React from 'react';
import { Form, Input, InputNumber, Select, type FormInstance } from 'antd';
import GroupTreeSelect from '@/components/group-tree-select';
import OperateFormModal from '@/components/operate-form-modal';
import { useTranslation } from '@/utils/i18n';
import {
  CONNECTION_CREDENTIAL_TYPES,
  type ConnectionCredentialType,
} from '@/app/system-manager/api/connection-credential';

export interface ConnectionCredentialFormValues {
  name: string;
  credential_type: ConnectionCredentialType | string;
  team: number[];
  username?: string;
  password?: string;
  community?: string;
  token?: string;
  port?: number;
}

interface ConnectionCredentialFormModalProps {
  open: boolean;
  editing: boolean;
  form: FormInstance<ConnectionCredentialFormValues>;
  saving?: boolean;
  onSubmit: () => void;
  onCancel: () => void;
}

const ConnectionCredentialFormModal: React.FC<ConnectionCredentialFormModalProps> = ({
  open,
  editing,
  form,
  saving = false,
  onSubmit,
  onCancel,
}) => {
  const { t } = useTranslation();
  const credentialType = Form.useWatch('credential_type', form);

  return (
    <OperateFormModal
      open={open}
      width={520}
      title={
        editing
          ? t('system.settings.connectionCredential.edit')
          : t('system.settings.connectionCredential.add')
      }
      confirmLoading={saving}
      onConfirm={onSubmit}
      onCancel={onCancel}
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="name"
          label={t('system.settings.connectionCredential.name')}
          rules={[{ required: true, message: t('system.settings.connectionCredential.nameRequired') }]}
        >
          <Input placeholder={t('system.settings.connectionCredential.namePlaceholder')} />
        </Form.Item>
        <Form.Item
          name="credential_type"
          label={t('system.settings.connectionCredential.type')}
          rules={[{ required: true, message: t('system.settings.connectionCredential.typeRequired') }]}
        >
          <Select
            options={CONNECTION_CREDENTIAL_TYPES.map((value) => ({
              value,
              label: t(`system.settings.connectionCredential.types.${value}`),
            }))}
          />
        </Form.Item>
        <Form.Item
          name="team"
          label={t('common.organization')}
          rules={[{ required: true, message: t('system.settings.connectionCredential.teamRequired') }]}
        >
          <GroupTreeSelect multiple placeholder={t('system.settings.connectionCredential.teamPlaceholder')} />
        </Form.Item>
        {credentialType !== 'snmp' && credentialType !== 'influxdb' && (
          <Form.Item name="username" label={t('common.username')}>
            <Input placeholder={t('system.settings.connectionCredential.usernamePlaceholder')} />
          </Form.Item>
        )}
        {credentialType === 'snmp' ? (
          <Form.Item
            name="community"
            label={t('system.settings.connectionCredential.community')}
            rules={editing ? [] : [{ required: true, message: t('system.settings.connectionCredential.communityRequired') }]}
          >
            <Input.Password placeholder={t('system.settings.connectionCredential.secretPlaceholder')} />
          </Form.Item>
        ) : credentialType === 'influxdb' ? (
          <Form.Item
            name="token"
            label={t('system.settings.connectionCredential.token')}
            rules={editing ? [] : [{ required: true, message: t('system.settings.connectionCredential.tokenRequired') }]}
          >
            <Input.Password placeholder={t('system.settings.connectionCredential.secretPlaceholder')} />
          </Form.Item>
        ) : (
          <Form.Item
            name="password"
            label={t('common.password')}
            rules={editing ? [] : [{ required: true, message: t('system.settings.connectionCredential.passwordRequired') }]}
          >
            <Input.Password placeholder={t('system.settings.connectionCredential.secretPlaceholder')} />
          </Form.Item>
        )}
        {credentialType !== 'snmp' && (
          <Form.Item name="port" label={t('system.settings.connectionCredential.port')}>
            <InputNumber min={1} max={65535} className="w-full" />
          </Form.Item>
        )}
      </Form>
    </OperateFormModal>
  );
};

export default ConnectionCredentialFormModal;
