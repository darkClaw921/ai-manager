import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Table, Tag, Select, DatePicker, Row, Col, Typography, Tooltip, Button, Popconfirm, message, theme } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { conversationsAPI } from '@/api'
import { useAuthStore } from '@/store/authStore'
import type { Conversation, ConversationStatus } from '@/types'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'

const { RangePicker } = DatePicker

const statusConfig: Record<ConversationStatus, { color: string; label: string }> = {
  active: { color: 'processing', label: 'Активный' },
  paused: { color: 'warning', label: 'Пауза' },
  completed: { color: 'success', label: 'Завершён' },
  handed_off: { color: 'orange', label: 'Передан' },
}

export default function ConversationsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const { token } = theme.useToken()
  const [searchParams, setSearchParams] = useSearchParams()
  const leadIdFilter = searchParams.get('lead_id')

  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)

  const params: Record<string, unknown> = { page, page_size: pageSize }
  if (statusFilter) params.status = statusFilter
  if (dateRange?.[0]) params.date_from = dateRange[0].toISOString()
  if (dateRange?.[1]) params.date_to = dateRange[1].toISOString()
  if (leadIdFilter) params.lead_id = leadIdFilter

  const { data, isLoading } = useQuery({
    queryKey: ['conversations', params],
    queryFn: () => conversationsAPI.getConversations(params).then((r) => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => conversationsAPI.deleteConversation(id),
    onSuccess: () => {
      message.success('Диалог удален')
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
    onError: () => {
      message.error('Ошибка удаления')
    },
  })

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
    setPageSize(pagination.pageSize ?? 20)
  }

  const columns: ColumnsType<Conversation> = [
    {
      title: 'Lead ID',
      dataIndex: 'lead_id',
      key: 'lead_id',
      render: (v: string) => v.slice(0, 8) + '...',
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (status: ConversationStatus, record: Conversation) => {
        const config = statusConfig[status]
        return (
          <div>
            <Tag color={config.color}>{config.label}</Tag>
            {status === 'handed_off' && record.manager_name && (
              <div style={{ fontSize: 11, color: token.colorTextSecondary, marginTop: 2 }}>
                {record.manager_name}
              </div>
            )}
          </div>
        )
      },
    },
    {
      title: 'Начат',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (v: string | null) => v ? dayjs(v).format('DD.MM.YYYY HH:mm') : '-',
      sorter: true,
    },
    {
      title: 'Создан',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => dayjs(v).format('DD.MM.YYYY HH:mm'),
      sorter: true,
    },
    ...(user?.role === 'admin' ? [{
      title: 'Действия',
      key: 'actions',
      render: (_: unknown, record: Conversation) => (
        <Popconfirm
          title="Удалить диалог?"
          description="Все сообщения будут удалены"
          onConfirm={(e) => {
            e?.stopPropagation()
            deleteMutation.mutate(record.id)
          }}
          onCancel={(e) => e?.stopPropagation()}
        >
          <Button
            danger
            icon={<DeleteOutlined />}
            size="small"
            onClick={(e) => e.stopPropagation()}
          />
        </Popconfirm>
      ),
    }] : []),
  ]

  return (
    <div>
      <Typography.Title level={4}>Диалоги</Typography.Title>

      {leadIdFilter && (
        <Tag
          closable
          onClose={() => {
            searchParams.delete('lead_id')
            setSearchParams(searchParams)
          }}
          style={{ marginBottom: 16 }}
        >
          Фильтр по лиду: {leadIdFilter.slice(0, 8)}...
        </Tag>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} md={6}>
          <Tooltip title="Фильтр диалогов по текущему статусу">
            <Select
              placeholder="Статус"
              allowClear
              style={{ width: '100%' }}
              onChange={(v) => { setStatusFilter(v); setPage(1) }}
              value={statusFilter}
              options={[
                { value: 'active', label: 'Активный' },
                { value: 'paused', label: 'Пауза' },
                { value: 'completed', label: 'Завершён' },
                { value: 'handed_off', label: 'Передан' },
              ]}
            />
          </Tooltip>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Tooltip title="Фильтр диалогов по дате создания">
            <RangePicker
              style={{ width: '100%' }}
              onChange={(dates) => {
                setDateRange(dates)
                setPage(1)
              }}
            />
          </Tooltip>
        </Col>
      </Row>

      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize,
          total: data?.total || 0,
          showSizeChanger: true,
          showTotal: (total) => `Всего: ${total}`,
        }}
        onChange={handleTableChange}
        onRow={(record) => ({
          onClick: () => navigate(`/conversations/${record.id}`),
          style: { cursor: 'pointer' },
        })}
      />
    </div>
  )
}
