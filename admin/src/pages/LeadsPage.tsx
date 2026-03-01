import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Table,
  Tag,
  Progress,
  Select,
  DatePicker,
  Input,
  Row,
  Col,
  Drawer,
  Descriptions,
  Button,
  Popconfirm,
  Typography,
  Space,
  Tooltip,
  Spin,
  Steps,
  Timeline,
  Divider,
  message,
} from 'antd'
import { CheckCircleOutlined, MinusCircleOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { leadsAPI } from '@/api'
import { useAuthStore } from '@/store/authStore'
import type { Lead, LeadStatus, ScoreBreakdownItem } from '@/types'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'

const { RangePicker } = DatePicker

const statusConfig: Record<LeadStatus, { color: string; label: string }> = {
  new: { color: 'blue', label: 'Новый' },
  qualifying: { color: 'processing', label: 'Квалификация' },
  qualified: { color: 'green', label: 'Квалифицирован' },
  booked: { color: 'purple', label: 'Записан' },
  handed_off: { color: 'orange', label: 'Передан' },
  lost: { color: 'default', label: 'Потерян' },
}

/** Stage ID to Russian label mapping (fallback for timeline when breakdown is unavailable) */
const stageLabels: Record<string, string> = {
  initial: 'Начало',
  needs_discovery: 'Выявление потребностей',
  budget_check: 'Обсуждение бюджета',
  timeline_check: 'Выяснение сроков',
  decision_maker: 'Определение ЛПР',
  qualified: 'Квалифицирован',
  booking_offer: 'Предложение записи',
  booked: 'Записан',
  handed_off: 'Передано менеджеру',
}

export default function LeadsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const user = useAuthStore((s) => s.user)

  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [search, setSearch] = useState<string | undefined>()
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)

  const params: Record<string, unknown> = { page, page_size: pageSize }
  if (statusFilter) params.status = statusFilter
  if (search) params.search = search
  if (dateRange?.[0]) params.date_from = dateRange[0].toISOString()
  if (dateRange?.[1]) params.date_to = dateRange[1].toISOString()

  const { data, isLoading } = useQuery({
    queryKey: ['leads', params],
    queryFn: () => leadsAPI.getLeads(params).then((r) => r.data),
  })

  const { data: freshLead, isLoading: isLeadLoading } = useQuery({
    queryKey: ['lead', selectedLead?.id],
    queryFn: () => leadsAPI.getLead(selectedLead!.id).then((r) => r.data),
    enabled: drawerOpen && !!selectedLead,
  })

  const displayLead = freshLead || selectedLead

  const deleteMutation = useMutation({
    mutationFn: (id: string) => leadsAPI.deleteLead(id),
    onSuccess: () => {
      message.success('Лид удален')
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      setDrawerOpen(false)
    },
    onError: () => {
      message.error('Ошибка удаления')
    },
  })

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
    setPageSize(pagination.pageSize ?? 20)
  }

  const openDrawer = (lead: Lead) => {
    setSelectedLead(lead)
    setDrawerOpen(true)
  }

  const columns: ColumnsType<Lead> = [
    {
      title: 'Имя',
      dataIndex: 'name',
      key: 'name',
      render: (v: string | null) => v || '-',
      sorter: true,
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
      render: (v: string | null) => v || '-',
    },
    {
      title: 'Телефон',
      dataIndex: 'phone',
      key: 'phone',
      render: (v: string | null) => v || '-',
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (status: LeadStatus) => {
        const config = statusConfig[status]
        return <Tag color={config.color}>{config.label}</Tag>
      },
    },
    {
      title: 'Этап',
      dataIndex: 'qualification_stage_label',
      key: 'qualification_stage_label',
      render: (v: string | null) => v || '-',
      responsive: ['md'],
    },
    {
      title: 'Interest Score',
      dataIndex: 'interest_score',
      key: 'interest_score',
      render: (score: number) => (
        <Progress
          percent={score}
          size="small"
          status={score >= 75 ? 'success' : score >= 50 ? 'normal' : 'exception'}
          style={{ width: 100 }}
        />
      ),
      sorter: true,
    },
    {
      title: 'Дата',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => dayjs(v).format('DD.MM.YYYY HH:mm'),
      sorter: true,
    },
    {
      title: 'Действия',
      key: 'actions',
      render: (_: unknown, record: Lead) => (
        <Space>
          <Button type="link" size="small" onClick={() => openDrawer(record)}>
            Подробнее
          </Button>
          {user?.role === 'admin' && (
            <Popconfirm
              title="Удалить лид?"
              onConfirm={() => deleteMutation.mutate(record.id)}
            >
              <Button type="link" size="small" danger>
                Удалить
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Typography.Title level={4}>Лиды</Typography.Title>

      {/* Filters */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} md={6}>
          <Tooltip title="Фильтр лидов по текущему статусу воронки">
            <Select
              placeholder="Статус"
              allowClear
              style={{ width: '100%' }}
              onChange={(v) => { setStatusFilter(v); setPage(1) }}
              value={statusFilter}
              options={[
                { value: 'new', label: 'Новый' },
                { value: 'qualifying', label: 'Квалификация' },
                { value: 'qualified', label: 'Квалифицирован' },
                { value: 'booked', label: 'Записан' },
                { value: 'handed_off', label: 'Передан' },
                { value: 'lost', label: 'Потерян' },
              ]}
            />
          </Tooltip>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Tooltip title="Фильтр лидов по дате создания">
            <RangePicker
              style={{ width: '100%' }}
              onChange={(dates) => {
                setDateRange(dates)
                setPage(1)
              }}
            />
          </Tooltip>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Tooltip title="Поиск по имени, email или телефону лида">
            <Input.Search
              placeholder="Поиск по имени/email/телефону"
              allowClear
              onSearch={(v) => { setSearch(v || undefined); setPage(1) }}
            />
          </Tooltip>
        </Col>
      </Row>

      {/* Table */}
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
          onClick: () => openDrawer(record),
          style: { cursor: 'pointer' },
        })}
      />

      {/* Lead Detail Drawer */}
      <Drawer
        title="Детали лида"
        placement="right"
        width={600}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        extra={
          <Space>
            <Button
              type="primary"
              onClick={() => {
                if (selectedLead?.id) {
                  const conv = selectedLead.id
                  navigate(`/conversations?lead_id=${conv}`)
                }
              }}
            >
              Диалоги
            </Button>
          </Space>
        }
      >
        {displayLead && (
          <Spin spinning={isLeadLoading}>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="ID">{displayLead.id}</Descriptions.Item>
              <Descriptions.Item label="Имя">{displayLead.name || '-'}</Descriptions.Item>
              <Descriptions.Item label="Email">{displayLead.email || '-'}</Descriptions.Item>
              <Descriptions.Item label="Телефон">{displayLead.phone || '-'}</Descriptions.Item>
              <Descriptions.Item label="Компания">{displayLead.company || '-'}</Descriptions.Item>
              <Descriptions.Item label="Статус">
                <Tag color={statusConfig[displayLead.status].color}>
                  {statusConfig[displayLead.status].label}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Interest Score">
                <Progress percent={displayLead.interest_score} size="small" style={{ width: 150 }} />
              </Descriptions.Item>
              <Descriptions.Item label="Этап квалификации">
                {displayLead.qualification_stage_label || displayLead.qualification_stage || '-'}
              </Descriptions.Item>
              {displayLead.qualification_script_name && (
                <Descriptions.Item label="Скрипт квалификации">
                  {displayLead.qualification_script_name}
                </Descriptions.Item>
              )}
              <Descriptions.Item label="Источник">{displayLead.source || '-'}</Descriptions.Item>
              <Descriptions.Item label="Канал">
                {displayLead.channel_name || '---'}
                {displayLead.channel_type && ` (${displayLead.channel_type})`}
              </Descriptions.Item>
              <Descriptions.Item label="Создан">
                {dayjs(displayLead.created_at).format('DD.MM.YYYY HH:mm')}
              </Descriptions.Item>
            </Descriptions>

            {/* Qualification Progress Steps */}
            {displayLead.score_breakdown && displayLead.score_breakdown.length > 0 && (
              <>
                <Divider titlePlacement="left">
                  <Typography.Text strong>Прогресс квалификации</Typography.Text>
                </Divider>
                <Steps
                  orientation="vertical"
                  size="small"
                  current={(() => {
                    const firstIncomplete = displayLead.score_breakdown!.findIndex((s: ScoreBreakdownItem) => !s.completed)
                    return firstIncomplete === -1 ? displayLead.score_breakdown!.length : firstIncomplete
                  })()}
                  items={displayLead.score_breakdown!.map((item: ScoreBreakdownItem, idx: number) => {
                    const firstIncomplete = displayLead.score_breakdown!.findIndex((s: ScoreBreakdownItem) => !s.completed)
                    const currentIdx = firstIncomplete === -1 ? displayLead.score_breakdown!.length : firstIncomplete
                    let status: 'finish' | 'process' | 'wait' = 'wait'
                    if (item.completed) {
                      status = 'finish'
                    } else if (idx === currentIdx) {
                      status = 'process'
                    }
                    return {
                      title: item.stage_label,
                      status,
                      content: (
                        <div>
                          <Typography.Text type="secondary">Вес: {item.weight}%</Typography.Text>
                          {item.collected_info && (
                            <div>
                              <Typography.Text style={{ fontSize: 12 }}>{item.collected_info}</Typography.Text>
                            </div>
                          )}
                        </div>
                      ),
                    }
                  })}
                />
              </>
            )}

            {/* Score Breakdown Table */}
            {displayLead.score_breakdown && displayLead.score_breakdown.length > 0 && (
              <>
                <Divider titlePlacement="left">
                  <Typography.Text strong>Разбивка оценки</Typography.Text>
                </Divider>
                <Table<ScoreBreakdownItem>
                  dataSource={displayLead.score_breakdown!}
                  rowKey="stage_id"
                  size="small"
                  pagination={false}
                  columns={[
                    {
                      title: 'Этап',
                      dataIndex: 'stage_label',
                      key: 'stage_label',
                    },
                    {
                      title: 'Вес',
                      dataIndex: 'weight',
                      key: 'weight',
                      width: 60,
                      render: (v: number) => `${v}%`,
                    },
                    {
                      title: 'Статус',
                      dataIndex: 'completed',
                      key: 'completed',
                      width: 70,
                      align: 'center' as const,
                      render: (completed: boolean) =>
                        completed ? (
                          <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
                        ) : (
                          <MinusCircleOutlined style={{ color: '#d9d9d9', fontSize: 16 }} />
                        ),
                    },
                    {
                      title: 'Собранная информация',
                      dataIndex: 'collected_info',
                      key: 'collected_info',
                      render: (v: string | null) => v || '-',
                    },
                  ]}
                />
              </>
            )}

            {/* Score History Timeline */}
            {Array.isArray(displayLead.qualification_data?._score_history) &&
              (displayLead.qualification_data!._score_history as Array<Record<string, unknown>>).length > 0 && (
              <>
                <Divider titlePlacement="left">
                  <Typography.Text strong>История Score</Typography.Text>
                </Divider>
                <Timeline
                  items={(displayLead.qualification_data._score_history as Array<{
                    stage: string
                    score_added: number
                    total_score: number
                    info: string
                  }>).map((entry) => {
                    const label = (() => {
                      if (displayLead.score_breakdown) {
                        const found = displayLead.score_breakdown.find((s: ScoreBreakdownItem) => s.stage_id === entry.stage)
                        if (found) return found.stage_label
                      }
                      return stageLabels[entry.stage] || entry.stage
                    })()
                    return {
                      color: 'green' as const,
                      content: (
                        <div>
                          <Typography.Text strong>{label}</Typography.Text>
                          {': '}
                          <Typography.Text type="success">+{entry.score_added}</Typography.Text>
                          <Typography.Text type="secondary">
                            {' -> '}{entry.total_score}/100
                          </Typography.Text>
                          {entry.info && (
                            <div>
                              <Typography.Text style={{ fontSize: 12 }} type="secondary">
                                {entry.info}
                              </Typography.Text>
                            </div>
                          )}
                        </div>
                      ),
                    }
                  })}
                />
              </>
            )}
          </Spin>
        )}
      </Drawer>
    </div>
  )
}
