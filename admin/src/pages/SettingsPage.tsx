import { useEffect, useState } from 'react'
import {
  Alert,
  AutoComplete,
  Card,
  Form,
  Input,
  InputNumber,
  Select,
  Button,
  Collapse,
  Checkbox,
  Typography,
  Spin,
  message,
  Badge,
  theme,
} from 'antd'
import { SaveOutlined, UndoOutlined, CodeOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsAPI } from '@/api'
import type { SystemSetting } from '@/types'

const { TextArea } = Input

const WEBHOOK_EXAMPLES: { event: string; label: string; payload: object }[] = [
  {
    event: 'new_lead',
    label: 'Новый лид',
    payload: {
      event: 'new_lead',
      lead_id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
      data: {
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        name: 'Иван Петров',
        email: 'ivan@example.com',
        phone: '+7 999 123-45-67',
        channel_type: 'telegram',
        interest_score: 0,
        qualification_stage: 'initial',
        qualification_data: {},
      },
      timestamp: '2026-03-01T12:00:00.000000+00:00',
    },
  },
  {
    event: 'qualified_lead',
    label: 'Лид квалифицирован',
    payload: {
      event: 'qualified_lead',
      lead_id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
      data: {
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        name: 'Иван Петров',
        email: 'ivan@example.com',
        phone: '+7 999 123-45-67',
        interest_score: 75,
        status: 'qualified',
        qualification_stage: 'decision_maker',
        qualification_data: {
          needs_discovery: 'Ищет CRM-систему для отдела продаж, 15 менеджеров',
          budget_check: 'Бюджет 500 000 руб., готов к ежемесячной подписке',
          timeline_check: 'Планирует внедрение в течение 2 месяцев',
          _score_history: [
            { stage: 'needs_discovery', score_added: 25, total_score: 25, info: 'CRM для отдела продаж' },
            { stage: 'budget_check', score_added: 25, total_score: 50, info: 'Бюджет 500к' },
            { stage: 'timeline_check', score_added: 25, total_score: 75, info: 'Внедрение за 2 мес.' },
          ],
        },
      },
      timestamp: '2026-03-01T12:05:00.000000+00:00',
    },
  },
  {
    event: 'booking',
    label: 'Запись на консультацию',
    payload: {
      event: 'booking',
      data: {
        id: 'b2c3d4e5-f6a7-8901-bcde-f12345678901',
        lead_name: 'Иван Петров',
        scheduled_at: '2026-03-05T14:00:00+03:00',
        duration_minutes: 30,
      },
      timestamp: '2026-03-01T12:10:00.000000+00:00',
    },
  },
  {
    event: 'handoff',
    label: 'Передача менеджеру',
    payload: {
      event: 'handoff',
      conversation_id: 'c3d4e5f6-a7b8-9012-cdef-123456789012',
      data: {
        id: 'c3d4e5f6-a7b8-9012-cdef-123456789012',
        lead_name: 'Иван Петров',
        lead_id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
      },
      timestamp: '2026-03-01T12:15:00.000000+00:00',
    },
  },
]

const MODEL_OPTIONS: Record<string, { value: string; label: string }[]> = {
  anthropic: [
    { value: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5' },
    { value: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4' },
    { value: 'claude-haiku-4-20250514', label: 'Claude Haiku 4' },
  ],
  openai: [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  ],
  openrouter: [
    { value: 'anthropic/claude-sonnet-4', label: 'Claude Sonnet 4 (via OpenRouter)' },
    { value: 'openai/gpt-4o', label: 'GPT-4o (via OpenRouter)' },
    { value: 'openai/gpt-5-nano', label: 'GPT-5 Nano (via OpenRouter)' },
    { value: 'google/gemini-2.0-flash', label: 'Gemini 2.0 Flash (via OpenRouter)' },
    { value: 'meta-llama/llama-3.1-70b-instruct', label: 'Llama 3.1 70B (via OpenRouter)' },
  ],
}

const PROVIDER_OPTIONS = [
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'openrouter', label: 'OpenRouter' },
]

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const [form] = Form.useForm()
  const [hasChanges, setHasChanges] = useState(false)
  const selectedProvider = Form.useWatch('llm_provider', form) || 'anthropic'
  const { token } = theme.useToken()

  const { data: settings, isLoading } = useQuery({
    queryKey: ['systemSettings'],
    queryFn: () => settingsAPI.getSettings().then((r) => r.data),
  })

  const saveMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => settingsAPI.updateSettings(data),
    onSuccess: () => {
      message.success('Настройки сохранены')
      queryClient.invalidateQueries({ queryKey: ['systemSettings'] })
      setHasChanges(false)
    },
    onError: () => {
      message.error('Ошибка сохранения')
    },
  })

  // Build a map of settings for easy access
  const settingsMap: Record<string, unknown> = {}
  if (settings) {
    settings.forEach((s: SystemSetting) => {
      settingsMap[s.key] = s.value
    })
  }

  // Initialize form when settings load
  useEffect(() => {
    if (settings) {
      form.setFieldsValue({
        llm_provider: settingsMap.llm_provider || 'anthropic',
        ai_model: settingsMap.ai_model || 'claude-sonnet-4-5',
        anthropic_api_key: settingsMap.anthropic_api_key || '',
        openai_api_key: settingsMap.openai_api_key || '',
        openrouter_api_key: settingsMap.openrouter_api_key || '',
        max_conversation_messages: settingsMap.max_conversation_messages || 50,
        qualification_timeout_hours: settingsMap.qualification_timeout_hours || 24,
        default_greeting: settingsMap.default_greeting || '',
        crm_webhook_url: settingsMap.crm_webhook_url || '',
        google_sheets_credentials: settingsMap.google_sheets_credentials || '',
        notification_webhook_url: settingsMap.notification_webhook_url || '',
        notification_email: settingsMap.notification_email || '',
        notification_telegram_chat_id: settingsMap.notification_telegram_chat_id || '',
        notification_events: settingsMap.notification_events || [],
      })
    }
  }, [settings, form]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = () => {
    form.validateFields().then((values) => {
      saveMutation.mutate(values)
    })
  }

  const handleReset = () => {
    if (settings) {
      const resetValues: Record<string, unknown> = {}
      settings.forEach((s: SystemSetting) => {
        resetValues[s.key] = s.value
      })
      form.setFieldsValue(resetValues)
      setHasChanges(false)
    }
  }

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Настройки системы
          {hasChanges && (
            <Badge count="Есть несохраненные изменения" style={{ marginLeft: 12, fontSize: 12 }} />
          )}
        </Typography.Title>
        <div>
          <Button icon={<UndoOutlined />} onClick={handleReset} disabled={!hasChanges} style={{ marginRight: 8 }}>
            Отменить
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={saveMutation.isPending}
            disabled={!hasChanges}
          >
            Сохранить все
          </Button>
        </div>
      </div>

      <Form
        form={form}
        layout="vertical"
        onValuesChange={() => setHasChanges(true)}
      >
        <Collapse defaultActiveKey={['ai', 'greeting']} style={{ marginBottom: 16 }}>
          <Collapse.Panel header="AI настройки" key="ai">
            <Form.Item name="llm_provider" label="LLM-провайдер" tooltip="Выберите провайдера AI-моделей. От выбора зависит список доступных моделей и какой API-ключ будет использоваться">
              <Select
                options={PROVIDER_OPTIONS}
                onChange={(value: string) => {
                  const models = MODEL_OPTIONS[value] || MODEL_OPTIONS.anthropic
                  form.setFieldsValue({ ai_model: models[0].value })
                }}
              />
            </Form.Item>
            <Form.Item
              name="ai_model"
              label="Модель AI"
              tooltip={selectedProvider === 'openrouter' ? 'Выберите из списка или введите ID модели вручную (например, provider/model-name)' : undefined}
            >
              {selectedProvider === 'openrouter' ? (
                <AutoComplete
                  options={MODEL_OPTIONS.openrouter}
                  placeholder="Выберите или введите ID модели..."
                  filterOption={(input, option) =>
                    (option?.value ?? '').toLowerCase().includes(input.toLowerCase()) ||
                    (option?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
                  }
                />
              ) : (
                <Select options={MODEL_OPTIONS[selectedProvider] || MODEL_OPTIONS.anthropic} />
              )}
            </Form.Item>
            <Form.Item
              name="anthropic_api_key"
              label={
                <span>
                  Anthropic API Key
                  {selectedProvider === 'anthropic' && (
                    <Badge count="Активный" style={{ marginLeft: 8, backgroundColor: '#52c41a' }} />
                  )}
                </span>
              }
              tooltip="Ключ для Anthropic API (Claude)"
            >
              <Input.Password placeholder="sk-ant-..." />
            </Form.Item>
            <Form.Item
              name="openai_api_key"
              label={
                <span>
                  OpenAI API Key
                  {selectedProvider === 'openai' && (
                    <Badge count="Активный" style={{ marginLeft: 8, backgroundColor: '#52c41a' }} />
                  )}
                </span>
              }
              tooltip="Ключ для OpenAI API (GPT)"
            >
              <Input.Password placeholder="sk-..." />
            </Form.Item>
            <Form.Item
              name="openrouter_api_key"
              label={
                <span>
                  OpenRouter API Key
                  {selectedProvider === 'openrouter' && (
                    <Badge count="Активный" style={{ marginLeft: 8, backgroundColor: '#52c41a' }} />
                  )}
                </span>
              }
              tooltip="Ключ для OpenRouter API"
            >
              <Input.Password placeholder="sk-or-..." />
            </Form.Item>
            <Alert
              type="info"
              showIcon
              message="API-ключи задаются здесь и хранятся в базе данных. Каждый менеджер может указать свой ключ."
              style={{ marginBottom: 16 }}
            />
            <Form.Item
              name="max_conversation_messages"
              label="Макс. сообщений в контексте"
              tooltip="Количество последних сообщений, загружаемых для AI"
            >
              <InputNumber min={10} max={200} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              name="qualification_timeout_hours"
              label="Таймаут квалификации (часы)"
              tooltip="Через сколько часов неактивный лид считается потерянным"
            >
              <InputNumber min={1} max={168} style={{ width: '100%' }} />
            </Form.Item>
          </Collapse.Panel>

          <Collapse.Panel header="Приветствие" key="greeting">
            <Form.Item name="default_greeting" label="Текст приветствия" tooltip="Первое сообщение, которое AI-бот отправляет новому пользователю. Задаёт тон общения и представляет возможности бота">
              <TextArea rows={4} placeholder="Здравствуйте! Я виртуальный ассистент..." />
            </Form.Item>
            <Card size="small" title="Предпросмотр" style={{ marginTop: 8, background: token.colorFillAlter }}>
              <Typography.Text>
                {form.getFieldValue('default_greeting') || 'Введите текст приветствия выше'}
              </Typography.Text>
            </Card>
          </Collapse.Panel>

          <Collapse.Panel header="Интеграции" key="integrations">
            <Form.Item
              name="crm_webhook_url"
              label="CRM Webhook URL"
              tooltip="URL для автоматической отправки данных о лидах в вашу CRM-систему. При квалификации лида данные отправляются POST-запросом"
              rules={[{ type: 'url', message: 'Введите корректный URL' }]}
            >
              <Input placeholder="https://..." />
            </Form.Item>
            <Form.Item name="google_sheets_credentials" label="Google Sheets Credentials (JSON)" tooltip="JSON-ключ сервисного аккаунта Google для экспорта лидов в Google Таблицы. Получите в Google Cloud Console → Service Accounts">
              <TextArea rows={3} placeholder='{"type": "service_account", ...}' style={{ fontFamily: 'monospace' }} />
            </Form.Item>
            <Form.Item
              name="notification_webhook_url"
              label="Webhook для уведомлений"
              tooltip="URL для отправки уведомлений о событиях. Поддерживаются Slack, Discord и другие сервисы с incoming webhooks"
              rules={[{ type: 'url', message: 'Введите корректный URL' }]}
            >
              <Input placeholder="https://..." />
            </Form.Item>
            <Collapse
              size="small"
              style={{ marginTop: -8, marginBottom: 16 }}
              items={[
                {
                  key: 'webhook-examples',
                  label: (
                    <span>
                      <CodeOutlined style={{ marginRight: 8 }} />
                      Примеры Webhook-запросов
                    </span>
                  ),
                  children: (
                    <div>
                      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
                        При наступлении события система отправляет <Typography.Text code>POST</Typography.Text> запрос
                        на указанный URL с JSON-телом. Заголовок: <Typography.Text code>Content-Type: application/json</Typography.Text>
                      </Typography.Text>
                      <Collapse
                        size="small"
                        items={WEBHOOK_EXAMPLES.map((ex) => ({
                          key: ex.event,
                          label: <Typography.Text strong>{ex.label}</Typography.Text>,
                          children: (
                            <pre
                              style={{
                                margin: 0,
                                padding: 12,
                                background: token.colorFillAlter,
                                borderRadius: token.borderRadiusSM,
                                fontSize: 12,
                                lineHeight: 1.6,
                                overflowX: 'auto',
                              }}
                            >
                              {JSON.stringify(ex.payload, null, 2)}
                            </pre>
                          ),
                        }))}
                      />
                    </div>
                  ),
                },
              ]}
            />
          </Collapse.Panel>

          <Collapse.Panel header="Уведомления" key="notifications">
            <Form.Item name="notification_email" label="Email для уведомлений" tooltip="На этот адрес будут приходить email-уведомления о выбранных событиях">
              <Input placeholder="admin@example.com" type="email" />
            </Form.Item>
            <Form.Item name="notification_telegram_chat_id" label="Telegram Chat ID для уведомлений" tooltip="ID Telegram-чата или группы для уведомлений. Узнайте ID через @userinfobot или из URL группы">
              <Input placeholder="-1001234567890" />
            </Form.Item>
            <Form.Item name="notification_events" label="Уведомлять о событиях" tooltip="Выберите события, по которым хотите получать уведомления. Отправляются во все настроенные каналы">
              <Checkbox.Group
                options={[
                  { label: 'Новый лид', value: 'new_lead' },
                  { label: 'Лид квалифицирован', value: 'lead_qualified' },
                  { label: 'Запись на консультацию', value: 'booking_created' },
                  { label: 'Передача менеджеру', value: 'handoff' },
                  { label: 'Лид потерян', value: 'lead_lost' },
                ]}
              />
            </Form.Item>
          </Collapse.Panel>
        </Collapse>
      </Form>
    </div>
  )
}
