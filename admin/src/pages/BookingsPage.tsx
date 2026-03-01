import { useState } from 'react'
import {
  Tabs,
  Table,
  Tag,
  Select,
  DatePicker,
  Button,
  Space,
  Form,
  Input,
  Checkbox,
  TimePicker,
  Card,
  Row,
  Col,
  Typography,
  Popconfirm,
  message,
  Spin,
  Empty,
  Tooltip,
} from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { bookingsAPI } from '@/api'
import type { Booking, BookingStatus, BookingSettings } from '@/types'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'

const { RangePicker } = DatePicker

const statusConfig: Record<BookingStatus, { color: string; label: string }> = {
  pending: { color: 'processing', label: 'Ожидание' },
  confirmed: { color: 'success', label: 'Подтверждена' },
  completed: { color: 'default', label: 'Завершена' },
  cancelled: { color: 'error', label: 'Отменена' },
  no_show: { color: 'warning', label: 'Не явился' },
}

const weekDays = [
  { label: 'Пн', value: 0 },
  { label: 'Вт', value: 1 },
  { label: 'Ср', value: 2 },
  { label: 'Чт', value: 3 },
  { label: 'Пт', value: 4 },
  { label: 'Сб', value: 5 },
  { label: 'Вс', value: 6 },
]

// --- Bookings List Tab ---

function BookingsListTab() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)

  const params: Record<string, unknown> = { page, page_size: pageSize }
  if (statusFilter) params.status = statusFilter
  if (dateRange?.[0]) params.date_from = dateRange[0].toISOString()
  if (dateRange?.[1]) params.date_to = dateRange[1].toISOString()

  const { data, isLoading } = useQuery({
    queryKey: ['bookings', params],
    queryFn: () => bookingsAPI.getBookings(params).then((r) => r.data),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data: d }: { id: string; data: Partial<Booking> }) => bookingsAPI.updateBooking(id, d),
    onSuccess: () => {
      message.success('Запись обновлена')
      queryClient.invalidateQueries({ queryKey: ['bookings'] })
    },
    onError: () => {
      message.error('Ошибка обновления')
    },
  })

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
    setPageSize(pagination.pageSize ?? 20)
  }

  const columns: ColumnsType<Booking> = [
    {
      title: 'Лид',
      dataIndex: 'lead_id',
      key: 'lead_id',
      render: (v: string) => v.slice(0, 8) + '...',
    },
    {
      title: 'Менеджер',
      dataIndex: 'manager_id',
      key: 'manager_id',
      render: (v: string | null) => v ? v.slice(0, 8) + '...' : '-',
    },
    {
      title: 'Дата/время',
      dataIndex: 'scheduled_at',
      key: 'scheduled_at',
      render: (v: string) => dayjs(v).format('DD.MM.YYYY HH:mm'),
      sorter: true,
    },
    {
      title: 'Длительность',
      dataIndex: 'duration_minutes',
      key: 'duration_minutes',
      render: (v: number) => `${v} мин`,
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (status: BookingStatus) => {
        const config = statusConfig[status]
        return <Tag color={config.color}>{config.label}</Tag>
      },
    },
    {
      title: 'Meeting Link',
      dataIndex: 'meeting_link',
      key: 'meeting_link',
      render: (v: string | null) =>
        v ? (
          <a href={v} target="_blank" rel="noopener noreferrer">
            Ссылка
          </a>
        ) : (
          '-'
        ),
    },
    {
      title: 'Действия',
      key: 'actions',
      render: (_: unknown, record: Booking) => (
        <Space>
          {record.status === 'pending' && (
            <>
              <Button
                size="small"
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={() => updateMutation.mutate({ id: record.id, data: { status: 'confirmed' } })}
              >
                Подтвердить
              </Button>
              <Popconfirm
                title="Отменить запись?"
                onConfirm={() => updateMutation.mutate({ id: record.id, data: { status: 'cancelled' } })}
              >
                <Button size="small" danger icon={<CloseCircleOutlined />}>
                  Отменить
                </Button>
              </Popconfirm>
            </>
          )}
          {record.status === 'confirmed' && (
            <Popconfirm
              title="Отменить запись?"
              onConfirm={() => updateMutation.mutate({ id: record.id, data: { status: 'cancelled' } })}
            >
              <Button size="small" danger icon={<CloseCircleOutlined />}>
                Отменить
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} md={6}>
          <Tooltip title="Фильтр записей по текущему статусу">
            <Select
              placeholder="Статус"
              allowClear
              style={{ width: '100%' }}
              onChange={(v) => { setStatusFilter(v); setPage(1) }}
              value={statusFilter}
              options={[
                { value: 'pending', label: 'Ожидание' },
                { value: 'confirmed', label: 'Подтверждена' },
                { value: 'completed', label: 'Завершена' },
                { value: 'cancelled', label: 'Отменена' },
                { value: 'no_show', label: 'Не явился' },
              ]}
            />
          </Tooltip>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Tooltip title="Фильтр записей по дате и времени">
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
      />
    </div>
  )
}

// --- Booking Settings Tab ---

function BookingSettingsTab() {
  const queryClient = useQueryClient()

  const { data: settingsList, isLoading } = useQuery({
    queryKey: ['bookingSettings'],
    queryFn: () => bookingsAPI.getSettings().then((r) => r.data),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data: d }: { id: string; data: Partial<BookingSettings> }) =>
      bookingsAPI.updateSettings(id, d),
    onSuccess: () => {
      message.success('Настройки сохранены')
      queryClient.invalidateQueries({ queryKey: ['bookingSettings'] })
    },
    onError: () => {
      message.error('Ошибка сохранения')
    },
  })

  if (isLoading) {
    return <Spin />
  }

  if (!settingsList || settingsList.length === 0) {
    return <Empty description="Нет настроек записи. Настройки создаются автоматически при добавлении менеджеров." />
  }

  return (
    <div>
      {settingsList.map((settings) => (
        <SettingsForm
          key={settings.id}
          settings={settings}
          onSave={(data) => updateMutation.mutate({ id: settings.id, data })}
          saving={updateMutation.isPending}
        />
      ))}
    </div>
  )
}

function SettingsForm({
  settings,
  onSave,
  saving,
}: {
  settings: BookingSettings
  onSave: (data: Partial<BookingSettings>) => void
  saving: boolean
}) {
  const [form] = Form.useForm()

  const handleSave = () => {
    form.validateFields().then((values) => {
      const hoursRange = values.available_hours
      onSave({
        available_days: values.available_days,
        available_hours: hoursRange
          ? {
              start: hoursRange[0]?.format('HH:mm') || '09:00',
              end: hoursRange[1]?.format('HH:mm') || '18:00',
            }
          : undefined,
        slot_duration: values.slot_duration,
        timezone: values.timezone,
        booking_link: values.booking_link,
        booking_mode: values.booking_mode,
      })
    })
  }

  const initialHours = settings.available_hours?.start && settings.available_hours?.end
    ? [
        dayjs(settings.available_hours.start, 'HH:mm'),
        dayjs(settings.available_hours.end, 'HH:mm'),
      ]
    : [dayjs('09:00', 'HH:mm'), dayjs('18:00', 'HH:mm')]

  return (
    <Card
      title={`Менеджер: ${settings.manager_name || settings.manager_id.slice(0, 8) + '...'}`}
      style={{ marginBottom: 16 }}
      extra={
        <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
          Сохранить
        </Button>
      }
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          available_days: settings.available_days || [0, 1, 2, 3, 4],
          available_hours: initialHours,
          slot_duration: settings.slot_duration || 30,
          timezone: settings.timezone || 'Europe/Moscow',
          booking_link: settings.booking_link || '',
          booking_mode: settings.booking_mode || 'internal',
        }}
      >
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="available_days" label="Рабочие дни" tooltip="Дни недели, в которые менеджер доступен для консультаций. AI-бот предлагает слоты только в эти дни">
              <Checkbox.Group options={weekDays} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="available_hours" label="Рабочие часы" tooltip="Временной интервал для записи. AI-бот предлагает только слоты в рамках этих часов">
              <TimePicker.RangePicker format="HH:mm" />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item name="slot_duration" label="Длительность слота" tooltip="Продолжительность одной консультации. Определяет шаг при генерации слотов">
              <Select
                options={[
                  { value: 15, label: '15 мин' },
                  { value: 30, label: '30 мин' },
                  { value: 45, label: '45 мин' },
                  { value: 60, label: '60 мин' },
                ]}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="timezone" label="Часовой пояс" tooltip="Часовой пояс менеджера. Все слоты рассчитываются и конвертируются для клиента">
              <Select
                options={[
                  { value: 'Europe/Moscow', label: 'Москва (UTC+3)' },
                  { value: 'Europe/Kaliningrad', label: 'Калининград (UTC+2)' },
                  { value: 'Asia/Yekaterinburg', label: 'Екатеринбург (UTC+5)' },
                  { value: 'Asia/Novosibirsk', label: 'Новосибирск (UTC+7)' },
                  { value: 'Asia/Vladivostok', label: 'Владивосток (UTC+10)' },
                ]}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="booking_mode" label="Режим записи" tooltip="Внутренний — встроенная система. Внешняя ссылка — перенаправление на Calendly. Передача менеджеру — уведомление без автозаписи">
              <Select
                options={[
                  { value: 'internal', label: 'Внутренний' },
                  { value: 'external_link', label: 'Внешняя ссылка' },
                  { value: 'handoff', label: 'Передача менеджеру' },
                ]}
              />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name="booking_link" label="Ссылка для записи" tooltip="Внешняя ссылка для записи (Calendly, Cal.com). Используется только в режиме 'Внешняя ссылка'">
          <Input placeholder="https://calendly.com/..." />
        </Form.Item>
      </Form>
    </Card>
  )
}

// --- Main BookingsPage ---

export default function BookingsPage() {
  return (
    <div>
      <Typography.Title level={4}>Записи на консультацию</Typography.Title>
      <Tabs
        defaultActiveKey="list"
        items={[
          { key: 'list', label: 'Записи', children: <BookingsListTab /> },
          { key: 'settings', label: 'Настройки записи', children: <BookingSettingsTab /> },
        ]}
      />
    </div>
  )
}
