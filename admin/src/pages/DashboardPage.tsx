import { useState, useCallback } from 'react'
import {
  Row,
  Col,
  Card,
  Statistic,
  Table,
  Spin,
  Empty,
  Typography,
  Radio,
  Button,
  Space,
  Tooltip as AntdTooltip,
  notification,
  theme as antdTheme,
} from 'antd'
import {
  TeamOutlined,
  MessageOutlined,
  CheckCircleOutlined,
  CalendarOutlined,
  DownloadOutlined,
  StarOutlined,
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'
import { analyticsAPI, leadsAPI, conversationsAPI } from '@/api'
import type { Lead, Conversation } from '@/types'
import type { ColumnsType } from 'antd/es/table'

const COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1', '#13c2c2']

const leadStatusLabels: Record<string, string> = {
  new: 'Новый',
  qualifying: 'Квалификация',
  qualified: 'Квалифицирован',
  booked: 'Записан',
  handed_off: 'Передан',
  lost: 'Потерян',
}

const periodOptions = [
  { label: '7 дней', value: '7d' },
  { label: '30 дней', value: '30d' },
  { label: '90 дней', value: '90d' },
]

const periodToDays: Record<string, number> = {
  '7d': 7,
  '30d': 30,
  '90d': 90,
}

export default function DashboardPage() {
  const [period, setPeriod] = useState('30d')
  const [exporting, setExporting] = useState(false)
  const { token } = antdTheme.useToken()

  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ['dashboard', period],
    queryFn: () => analyticsAPI.getDashboard({ period }).then((r) => r.data),
    refetchInterval: 60000,
  })

  const { data: leadStats, isLoading: statsLoading } = useQuery({
    queryKey: ['leadStats', period],
    queryFn: () =>
      analyticsAPI.getLeadStats({ days: periodToDays[period] || 30 }).then((r) => r.data),
    refetchInterval: 60000,
  })

  const { data: funnel, isLoading: funnelLoading } = useQuery({
    queryKey: ['funnel'],
    queryFn: () => analyticsAPI.getConversionFunnel().then((r) => r.data),
    refetchInterval: 60000,
  })

  const { data: recentLeads } = useQuery({
    queryKey: ['recentLeads'],
    queryFn: () => leadsAPI.getLeads({ page: 1, page_size: 10 }).then((r) => r.data),
    refetchInterval: 60000,
  })

  const { data: recentConversations } = useQuery({
    queryKey: ['recentConversations'],
    queryFn: () =>
      conversationsAPI.getConversations({ page: 1, page_size: 5 }).then((r) => r.data),
    refetchInterval: 60000,
  })

  const handleExportCSV = useCallback(async () => {
    setExporting(true)
    try {
      const response = await analyticsAPI.exportCSV()
      const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `leads_export_${new Date().toISOString().slice(0, 10)}.csv`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      notification.success({ message: 'CSV экспортирован' })
    } catch {
      notification.error({ message: 'Ошибка экспорта CSV' })
    } finally {
      setExporting(false)
    }
  }, [])

  if (dashLoading || statsLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!dashboard) {
    return <Empty description="Нет данных" />
  }

  // Prepare bar chart data from leads_by_status
  const statusData = leadStats?.leads_by_status
    ? Object.entries(leadStats.leads_by_status).map(([status, count]) => ({
        status: leadStatusLabels[status] || status,
        count,
      }))
    : []

  // Prepare pie chart data from leads_by_channel
  const channelData = leadStats?.leads_by_channel
    ? Object.entries(leadStats.leads_by_channel).map(([channel, count]) => ({
        name: channel === 'unknown' ? 'Неизвестный' : channel,
        value: count,
      }))
    : []

  const leadColumns: ColumnsType<Lead> = [
    {
      title: 'Имя',
      dataIndex: 'name',
      key: 'name',
      render: (v: string | null) => v || '-',
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
      render: (v: string | null) => v || '-',
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => leadStatusLabels[v] || v,
    },
    { title: 'Score', dataIndex: 'interest_score', key: 'interest_score' },
  ]

  const conversationColumns: ColumnsType<Conversation> = [
    {
      title: 'Lead ID',
      dataIndex: 'lead_id',
      key: 'lead_id',
      render: (v: string) => v.slice(0, 8) + '...',
    },
    { title: 'Статус', dataIndex: 'status', key: 'status' },
    {
      title: 'Создан',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString('ru-RU'),
    },
  ]

  return (
    <div>
      {/* Header with title, period filter, and export button */}
      <Row
        justify="space-between"
        align="middle"
        style={{ marginBottom: 24 }}
      >
        <Col>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Дашборд
          </Typography.Title>
        </Col>
        <Col>
          <Space>
            <AntdTooltip title="Период для расчёта статистики. Влияет на графики и показатели">
              <Radio.Group
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                optionType="button"
                buttonStyle="solid"
                options={periodOptions}
              />
            </AntdTooltip>
            <Button
              icon={<DownloadOutlined />}
              onClick={handleExportCSV}
              loading={exporting}
            >
              Скачать CSV
            </Button>
          </Space>
        </Col>
      </Row>

      {/* Statistic Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic
              title="Всего лидов"
              value={dashboard.total_leads}
              prefix={<TeamOutlined />}
              suffix={
                <span style={{ fontSize: 12, color: token.colorTextSecondary }}>
                  +{dashboard.leads_today} сегодня
                </span>
              }
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic
              title="За неделю"
              value={dashboard.leads_week}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic
              title="За месяц"
              value={dashboard.leads_month}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic
              title="Активных диалогов"
              value={dashboard.active_conversations}
              prefix={<MessageOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic
              title="Квалификация"
              value={dashboard.qualification_rate}
              prefix={<CheckCircleOutlined />}
              suffix="%"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic
              title="Записей"
              value={dashboard.bookings_count}
              prefix={<CalendarOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* Average interest score card */}
      {dashboard.avg_interest_score > 0 && (
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={24} sm={12} md={8} lg={4}>
            <Card>
              <Statistic
                title="Средний Score"
                value={dashboard.avg_interest_score}
                prefix={<StarOutlined />}
                precision={1}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Charts Row 1: Line (leads per day) + Bar (by status) */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card
            title={`Новые лиды за ${periodToDays[period] || 30} дней`}
            loading={statsLoading}
          >
            {leadStats?.leads_by_day && leadStats.leads_by_day.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={leadStats.leads_by_day}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="count"
                    name="Лиды"
                    stroke="#1677ff"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <Empty description="Нет данных за период" />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Лиды по статусам" loading={statsLoading}>
            {statusData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={statusData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="status" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" name="Кол-во" fill="#1677ff">
                    {statusData.map((_entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={COLORS[index % COLORS.length]}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Empty description="Нет данных" />
            )}
          </Card>
        </Col>
      </Row>

      {/* Charts Row 2: Pie (by channel) + Funnel */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card title="Лиды по каналам" loading={statsLoading}>
            {channelData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={channelData}
                    cx="50%"
                    cy="50%"
                    labelLine={true}
                    label={({ name, percent }) =>
                      `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`
                    }
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {channelData.map((_entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={COLORS[index % COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Empty description="Нет данных" />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Воронка конверсии" loading={funnelLoading}>
            {funnel?.stages && funnel.stages.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={funnel.stages.map((s) => ({
                    stage: leadStatusLabels[s.stage] || s.stage,
                    count: s.count,
                  }))}
                  layout="vertical"
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" allowDecimals={false} />
                  <YAxis dataKey="stage" type="category" width={120} />
                  <Tooltip />
                  <Bar dataKey="count" name="Лиды" fill="#52c41a">
                    {funnel.stages.map((_entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={COLORS[index % COLORS.length]}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Empty description="Нет данных" />
            )}
          </Card>
        </Col>
      </Row>

      {/* Recent Activity */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="Последние лиды">
            <Table
              dataSource={recentLeads?.items || []}
              columns={leadColumns}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="Последние диалоги">
            <Table
              dataSource={recentConversations?.items || []}
              columns={conversationColumns}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
