import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Tag, Button, Typography, message, Alert } from 'antd'
import { LoginOutlined } from '@ant-design/icons'
import { managersAPI } from '@/api'
import { useImpersonationStore } from '@/store/impersonationStore'
import type { ManagerWithStats } from '@/types'
import type { ColumnsType } from 'antd/es/table'

export default function ManagersPage() {
  const navigate = useNavigate()
  const startImpersonation = useImpersonationStore((s) => s.startImpersonation)

  const [managers, setManagers] = useState<ManagerWithStats[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    managersAPI
      .getAll()
      .then((res) => {
        setManagers(res.data)
      })
      .catch(() => {
        setError('Не удалось загрузить список менеджеров')
        message.error('Ошибка загрузки менеджеров')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  const handleImpersonate = (manager: ManagerWithStats) => {
    startImpersonation(manager.id, manager.full_name)
    navigate('/dashboard')
  }

  const columns: ColumnsType<ManagerWithStats> = [
    {
      title: 'Имя',
      dataIndex: 'full_name',
      key: 'full_name',
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: 'Каналов',
      dataIndex: 'channels_count',
      key: 'channels_count',
      align: 'center',
    },
    {
      title: 'Лидов',
      dataIndex: 'leads_count',
      key: 'leads_count',
      align: 'center',
    },
    {
      title: 'Диалогов',
      dataIndex: 'conversations_count',
      key: 'conversations_count',
      align: 'center',
    },
    {
      title: 'Статус',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive: boolean) =>
        isActive ? (
          <Tag color="green">Активен</Tag>
        ) : (
          <Tag color="red">Неактивен</Tag>
        ),
    },
    {
      title: 'Действия',
      key: 'actions',
      render: (_: unknown, record: ManagerWithStats) => (
        <Button
          type="link"
          icon={<LoginOutlined />}
          onClick={() => handleImpersonate(record)}
        >
          Войти как менеджер
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Typography.Title level={4}>Менеджеры</Typography.Title>

      {error && (
        <Alert
          message={error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Table
        dataSource={managers}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{
          showTotal: (total) => `Всего: ${total}`,
        }}
      />
    </div>
  )
}
