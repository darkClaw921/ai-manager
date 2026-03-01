import { useState } from 'react'
import {
  Card,
  Row,
  Col,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  Tag,
  Typography,
  Space,
  Popconfirm,
  message,
  Spin,
  Empty,
} from 'antd'
import {
  PlusOutlined,
  ApiOutlined,
  MessageOutlined,
  CopyOutlined,
  ExperimentOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { channelsAPI, scriptsAPI } from '@/api'
import type { Channel, ChannelType } from '@/types'

const channelTypeConfig: Record<ChannelType, { icon: React.ReactNode; label: string; color: string }> = {
  telegram: { icon: <MessageOutlined />, label: 'Telegram', color: '#0088cc' },
  web_widget: { icon: <ApiOutlined />, label: 'Web Widget', color: '#52c41a' },
}

export default function ChannelsPage() {
  const queryClient = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [editingChannel, setEditingChannel] = useState<Channel | null>(null)
  const [form] = Form.useForm()
  const channelType = Form.useWatch('type', form)

  const { data, isLoading } = useQuery({
    queryKey: ['channels'],
    queryFn: () => channelsAPI.getChannels({ page_size: 100 }).then((r) => r.data),
  })

  const { data: scriptsData } = useQuery({
    queryKey: ['qualificationScripts'],
    queryFn: () => scriptsAPI.getScripts().then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (d: Partial<Channel>) => channelsAPI.createChannel(d),
    onSuccess: () => {
      message.success('Канал создан')
      queryClient.invalidateQueries({ queryKey: ['channels'] })
      setModalOpen(false)
      form.resetFields()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data: d }: { id: string; data: Partial<Channel> }) => channelsAPI.updateChannel(id, d),
    onSuccess: () => {
      message.success('Канал обновлен')
      queryClient.invalidateQueries({ queryKey: ['channels'] })
      setModalOpen(false)
      setEditingChannel(null)
      form.resetFields()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => channelsAPI.deleteChannel(id),
    onSuccess: () => {
      message.success('Канал удален')
      queryClient.invalidateQueries({ queryKey: ['channels'] })
    },
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      channelsAPI.updateChannel(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] })
    },
  })

  const testMutation = useMutation({
    mutationFn: (id: string) => channelsAPI.testChannel(id),
    onSuccess: (res) => {
      if (res.data.status === 'ok') {
        message.success(res.data.message)
      } else {
        message.warning(res.data.message)
      }
    },
    onError: () => {
      message.error('Ошибка тестирования')
    },
  })

  const openCreate = () => {
    setEditingChannel(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (channel: Channel) => {
    setEditingChannel(channel)
    const config = channel.config as Record<string, unknown> || {}
    form.setFieldsValue({
      type: channel.type,
      name: channel.name,
      is_active: channel.is_active,
      qualification_script_id: channel.qualification_script_id || undefined,
      bot_token: config.bot_token || '',
      bot_mode: config.bot_mode || 'webhook',
      allowed_origins: config.allowed_origins || '',
      theme_color: config.theme_color || '#1677ff',
    })
    setModalOpen(true)
  }

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      const config: Record<string, unknown> = {}
      if (values.type === 'telegram') {
        config.bot_token = values.bot_token || ''
        config.bot_mode = values.bot_mode || 'webhook'
      } else {
        config.allowed_origins = values.allowed_origins || ''
        config.theme_color = values.theme_color || '#1677ff'
      }

      const d = {
        type: values.type,
        name: values.name,
        config,
        is_active: values.is_active ?? true,
        qualification_script_id: values.qualification_script_id || null,
      }

      if (editingChannel) {
        updateMutation.mutate({ id: editingChannel.id, data: d })
      } else {
        createMutation.mutate(d)
      }
    })
  }

  const copyEmbedCode = (channelId: string) => {
    const code = `<script src="${window.location.origin}/widget/embed.js" data-channel-id="${channelId}"></script>`
    navigator.clipboard.writeText(code).then(() => {
      message.success('Код скопирован')
    })
  }

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin size="large" />
      </div>
    )
  }

  const channels = data?.items || []

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>Каналы</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Добавить канал
        </Button>
      </div>

      {channels.length === 0 ? (
        <Empty description="Нет каналов" />
      ) : (
        <Row gutter={[16, 16]}>
          {channels.map((channel) => {
            const typeConfig = channelTypeConfig[channel.type]
            return (
              <Col xs={24} sm={12} lg={8} key={channel.id}>
                <Card
                  actions={[
                    <Button
                      key="test"
                      type="text"
                      icon={<ExperimentOutlined />}
                      onClick={() => testMutation.mutate(channel.id)}
                      loading={testMutation.isPending}
                    >
                      Тест
                    </Button>,
                    <Button key="edit" type="text" icon={<EditOutlined />} onClick={() => openEdit(channel)}>
                      Ред.
                    </Button>,
                    <Popconfirm key="delete" title="Удалить канал?" onConfirm={() => deleteMutation.mutate(channel.id)}>
                      <Button type="text" danger icon={<DeleteOutlined />}>
                        Удалить
                      </Button>
                    </Popconfirm>,
                  ]}
                >
                  <Card.Meta
                    avatar={
                      <div style={{ fontSize: 24, color: typeConfig.color }}>
                        {typeConfig.icon}
                      </div>
                    }
                    title={
                      <Space>
                        {channel.name}
                        <Tag color={typeConfig.color}>{typeConfig.label}</Tag>
                      </Space>
                    }
                    description={
                      <div>
                        <div style={{ marginBottom: 8 }}>
                          <Switch
                            checked={channel.is_active}
                            onChange={(checked) =>
                              toggleMutation.mutate({ id: channel.id, is_active: checked })
                            }
                            checkedChildren="Активен"
                            unCheckedChildren="Неактивен"
                          />
                        </div>
                        {channel.type === 'telegram' && (
                          <div style={{ marginTop: 4 }}>
                            <Tag color={(channel.config as Record<string, unknown>)?.bot_mode === 'polling' ? 'orange' : 'blue'}>
                              {(channel.config as Record<string, unknown>)?.bot_mode === 'polling' ? 'Long Polling' : 'Webhook'}
                            </Tag>
                          </div>
                        )}
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          Создан: {dayjs(channel.created_at).format('DD.MM.YYYY')}
                        </Typography.Text>
                        {channel.qualification_script_name && (
                          <div style={{ marginTop: 4 }}>
                            <Tag color="purple">{channel.qualification_script_name}</Tag>
                          </div>
                        )}
                        {channel.type === 'web_widget' && (
                          <div style={{ marginTop: 8 }}>
                            <Button
                              size="small"
                              icon={<CopyOutlined />}
                              onClick={() => copyEmbedCode(channel.id)}
                            >
                              Копировать embed code
                            </Button>
                          </div>
                        )}
                      </div>
                    }
                  />
                </Card>
              </Col>
            )
          })}
        </Row>
      )}

      <Modal
        title={editingChannel ? 'Редактировать канал' : 'Новый канал'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => { setModalOpen(false); setEditingChannel(null); form.resetFields() }}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="type" label="Тип" rules={[{ required: true, message: 'Выберите тип' }]} tooltip="Telegram — интеграция с Telegram-ботом. Web Widget — встраивание чата на ваш сайт">
            <Select
              disabled={!!editingChannel}
              options={[
                { value: 'telegram', label: 'Telegram' },
                { value: 'web_widget', label: 'Web Widget' },
              ]}
            />
          </Form.Item>
          <Form.Item name="name" label="Название" rules={[{ required: true, message: 'Введите название' }]} tooltip="Уникальное название канала для отображения в списке. Например: 'Основной бот' или 'Виджет на сайте'">
            <Input />
          </Form.Item>

          {/* Telegram config */}
          {channelType === 'telegram' && (
            <>
              <Form.Item name="bot_token" label="Bot Token" tooltip="Токен от @BotFather. Webhook будет зарегистрирован автоматически.">
                <Input.Password placeholder="123456:ABC-DEF..." />
              </Form.Item>
              <Form.Item name="bot_mode" label="Режим получения обновлений" initialValue="webhook" tooltip="Webhook — мгновенное получение сообщений (рекомендуется для продакшена). Long Polling — бот сам опрашивает Telegram (для разработки)">
                <Select
                  options={[
                    { value: 'webhook', label: 'Webhook (рекомендуется)' },
                    { value: 'polling', label: 'Long Polling' },
                  ]}
                />
              </Form.Item>
            </>
          )}

          {/* Web Widget config */}
          {channelType === 'web_widget' && (
            <>
              <Form.Item name="allowed_origins" label="Allowed Origins" tooltip="Домен сайта, на котором будет установлен виджет. Ограничивает подключение к чату (CORS). Например: https://example.com">
                <Input placeholder="https://example.com" />
              </Form.Item>
              <Form.Item name="theme_color" label="Theme Color" initialValue="#1677ff" tooltip="Основной цвет виджета чата. Применяется к кнопке, заголовку и элементам интерфейса виджета">
                <Input type="color" style={{ width: 60 }} />
              </Form.Item>
            </>
          )}

          <Form.Item name="is_active" label="Активен" valuePropName="checked" initialValue={true} tooltip="Неактивный канал не принимает входящие сообщения. Используйте для временного отключения без удаления">
            <Switch />
          </Form.Item>

          <Form.Item
            name="qualification_script_id"
            label="Скрипт квалификации"
            tooltip="Назначить скрипт для этого канала. Если не выбран — используется глобальный активный скрипт"
          >
            <Select
              allowClear
              placeholder="Глобальный активный скрипт"
              options={(scriptsData || []).map((s) => ({ value: s.id, label: s.name }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
