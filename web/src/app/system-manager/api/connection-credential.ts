import { useCallback } from 'react';
import useApiClient from '@/utils/request';

export const CONNECTION_CREDENTIAL_SECRET_MASK = '******';

export const CONNECTION_CREDENTIAL_TYPES = [
  'host',
  'ssh',
  'mysql',
  'postgresql',
  'mssql',
  'snmp',
  'influxdb',
] as const;

export type ConnectionCredentialType = (typeof CONNECTION_CREDENTIAL_TYPES)[number];

export interface ConnectionCredentialListItem {
  id: number;
  name: string;
  credential_type: string;
  username: string;
  team: number[];
  created_at?: string;
  updated_at?: string;
  created_by?: string;
  updated_by?: string;
}

export interface ConnectionCredentialDetail extends ConnectionCredentialListItem {
  payload: Record<string, unknown>;
}

export interface ConnectionCredentialPage {
  count: number;
  items: ConnectionCredentialListItem[];
}

export interface ConnectionCredentialWritePayload {
  name: string;
  credential_type: string;
  team: number[];
  payload: Record<string, unknown>;
}

export const useConnectionCredentialApi = () => {
  const { get, post, put, del } = useApiClient();

  const fetchConnectionCredentials = useCallback(
    async (page: number, pageSize: number, search?: string): Promise<ConnectionCredentialPage> => {
      const params: Record<string, string | number> = { page, page_size: pageSize };
      if (search) {
        params.name = search;
      }
      const data = await get('/system_mgmt/connection_credential/', { params });
      if (Array.isArray(data)) {
        return { count: data.length, items: data };
      }
      return {
        count: Number(data?.count || 0),
        items: data?.items || data?.results || [],
      };
    },
    [get]
  );

  const getConnectionCredential = useCallback(
    async (id: number): Promise<ConnectionCredentialDetail> => {
      return get(`/system_mgmt/connection_credential/${id}/`);
    },
    [get]
  );

  const createConnectionCredential = useCallback(
    async (body: ConnectionCredentialWritePayload): Promise<ConnectionCredentialDetail> => {
      return post('/system_mgmt/connection_credential/', body);
    },
    [post]
  );

  const updateConnectionCredential = useCallback(
    async (id: number, body: ConnectionCredentialWritePayload): Promise<ConnectionCredentialDetail> => {
      return put(`/system_mgmt/connection_credential/${id}/`, body);
    },
    [put]
  );

  const deleteConnectionCredential = useCallback(
    async (id: number): Promise<void> => {
      await del(`/system_mgmt/connection_credential/${id}/`);
    },
    [del]
  );

  return {
    fetchConnectionCredentials,
    getConnectionCredential,
    createConnectionCredential,
    updateConnectionCredential,
    deleteConnectionCredential,
  };
};
