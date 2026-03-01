import { useState } from 'react'
import {
  Table,
  Tag,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  Popconfirm,
  Typography,
  message,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { usersAPI } from '@/api'
import type { AdminUser } from '@/types'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import { useAuthStore } from '@/store/authStore'

export default function UsersPage() {
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const [page, setPage] = useState(1)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null)
  const [form] = Form.useForm()

  const { data, isLoading } = useQuery({
    queryKey: ['users', page],
    queryFn: () => usersAPI.getUsers({ page, page_size: 20 }).then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (d: { email: string; password: string; full_name: string; role: string }) => usersAPI.createUser(d),
    onSuccess: () => {
      message.success('Пользователь создан')
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setModalOpen(false)
      form.resetFields()
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      message.error(error.response?.data?.detail || 'Ошибка создания')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data: d }: { id: string; data: Partial<AdminUser & { password?: string }> }) =>
      usersAPI.updateUser(id, d),
    onSuccess: () => {
      message.success('Пользователь обновлен')
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setModalOpen(false)
      setEditingUser(null)
      form.resetFields()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => usersAPI.deleteUser(id),
    onSuccess: () => {
      message.success('Пользователь удален')
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      message.error(error.response?.data?.detail || 'Ошибка удаления')
    },
  })

  const openCreate = () => {
    setEditingUser(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (user: AdminUser) => {
    setEditingUser(user)
    form.setFieldsValue({
      email: user.email,
      full_name: user.full_name,
      role: user.role,
      is_active: user.is_active,
    })
    setModalOpen(true)
  }

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      if (editingUser) {
        const updateData: Record<string, unknown> = {
          email: values.email,
          full_name: values.full_name,
          role: values.role,
          is_active: values.is_active,
        }
        if (values.password) {
          updateData.password = values.password
        }
        updateMutation.mutate({ id: editingUser.id, data: updateData })
      } else {
        createMutation.mutate({
          email: values.email,
          password: values.password,
          full_name: values.full_name,
          role: values.role,
        })
      }
    })
  }

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
  }

  const columns: ColumnsType<AdminUser> = [
    { title: 'Имя', dataIndex: 'full_name', key: 'full_name' },
    { title: 'Email', dataIndex: 'email', key: 'email' },
    {
      title: 'Роль',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) =>
        role === 'admin' ? <Tag color="red">Администратор</Tag> : <Tag color="blue">Менеджер</Tag>,
    },
    {
      title: 'Статус',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (v: boolean) => v ? <Tag color="green">Активен</Tag> : <Tag>Неактивен</Tag>,
    },
    {
      title: 'Создан',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => dayjs(v).format('DD.MM.YYYY'),
    },
    {
      title: 'Действия',
      key: 'actions',
      render: (_: unknown, record: AdminUser) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          {record.id !== currentUser?.id && (
            <Popconfirm title="Удалить пользователя?" onConfirm={() => deleteMutation.mutate(record.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>Пользователи</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Добавить пользователя
        </Button>
      </div>

      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize: 20,
          total: data?.total || 0,
          showTotal: (total) => `Всего: ${total}`,
        }}
        onChange={handleTableChange}
      />

      <Modal
        title={editingUser ? 'Редактировать пользователя' : 'Новый пользователь'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => { setModalOpen(false); setEditingUser(null); form.resetFields() }}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="email"
            label="Email"
            tooltip="Email для входа в админ-панель. Также используется для email-уведомлений"
            rules={[
              { required: true, message: 'Введите email' },
              { type: 'email', message: 'Некорректный email' },
            ]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="password"
            label={editingUser ? 'Новый пароль (оставьте пустым для сохранения текущего)' : 'Пароль'}
            tooltip="Пароль для входа в систему. Минимум 6 символов"
            rules={editingUser ? [] : [{ required: true, message: 'Введите пароль' }, { min: 6, message: 'Минимум 6 символов' }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="full_name"
            label="Полное имя"
            tooltip="Имя пользователя для отображения в интерфейсе и назначениях лидов"
            rules={[{ required: true, message: 'Введите имя' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="role" label="Роль" tooltip="Администратор — полный доступ. Менеджер — доступ к лидам, диалогам и записям" initialValue="manager">
            <Select
              options={[
                { value: 'admin', label: 'Администратор' },
                { value: 'manager', label: 'Менеджер' },
              ]}
            />
          </Form.Item>
          {editingUser && (
            <Form.Item name="is_active" label="Активен" tooltip="Неактивный пользователь не может войти в систему. Используйте вместо удаления" valuePropName="checked">
              <Switch />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  )
}
