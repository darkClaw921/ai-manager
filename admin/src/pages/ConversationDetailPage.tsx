import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card,
  Button,
  Tag,
  Descriptions,
  Spin,
  Empty,
  Typography,
  Space,
  Input,
  message,
  theme,
} from 'antd'
import {
  ArrowLeftOutlined,
  PauseCircleOutlined,
  CheckCircleOutlined,
  SwapOutlined,
  SendOutlined,
  RobotOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { conversationsAPI } from '@/api'
import type { Message, ConversationStatus } from '@/types'

const statusConfig: Record<ConversationStatus, { color: string; label: string }> = {
  active: { color: 'processing', label: 'Активный' },
  paused: { color: 'warning', label: 'Пауза' },
  completed: { color: 'success', label: 'Завершён' },
  handed_off: { color: 'orange', label: 'Передан' },
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  const isSystem = msg.role === 'system'
  const isManager = msg.role === 'assistant' && msg.metadata_?.sender === 'manager'
  const { token } = theme.useToken()

  if (isSystem) {
    return (
      <div style={{ textAlign: 'center', margin: '8px 0' }}>
        <Tag color="gold" style={{ fontSize: 12 }}>
          {msg.content}
        </Tag>
        <div style={{ fontSize: 10, color: token.colorTextSecondary, marginTop: 2 }}>
          {dayjs(msg.created_at).format('HH:mm')}
        </div>
      </div>
    )
  }

  const managerName = isManager ? (msg.metadata_?.manager_name as string) : null

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 12,
      }}
    >
      <div
        style={{
          maxWidth: '70%',
          padding: '10px 14px',
          borderRadius: 12,
          backgroundColor: isUser ? token.colorPrimary : isManager ? token.colorPrimaryBg : token.colorBgTextHover,
          color: isUser ? token.colorTextLightSolid : token.colorText,
          border: isManager ? `1px solid ${token.colorPrimaryBorder}` : 'none',
          wordBreak: 'break-word',
          whiteSpace: 'pre-wrap',
        }}
      >
        <div style={{ fontSize: 10, fontWeight: 600, marginBottom: 2, opacity: 0.7 }}>
          {isUser ? 'Пользователь' : isManager ? `Менеджер${managerName ? ` (${managerName})` : ''}` : 'Ассистент'}
        </div>
        <div>{msg.content}</div>
        <div
          style={{
            fontSize: 10,
            textAlign: 'right',
            marginTop: 4,
            opacity: 0.6,
          }}
        >
          {dayjs(msg.created_at).format('HH:mm')}
        </div>
      </div>
    </div>
  )
}

export default function ConversationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [messageText, setMessageText] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { token } = theme.useToken()

  const { data: conversation, isLoading } = useQuery({
    queryKey: ['conversation', id],
    queryFn: () => conversationsAPI.getConversation(id!).then((r) => r.data),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'active' || status === 'handed_off' ? 3000 : false
    },
  })

  const statusMutation = useMutation({
    mutationFn: (newStatus: string) => conversationsAPI.updateStatus(id!, newStatus),
    onSuccess: () => {
      message.success('Статус обновлен')
      queryClient.invalidateQueries({ queryKey: ['conversation', id] })
    },
    onError: () => {
      message.error('Ошибка обновления статуса')
    },
  })

  const sendMessageMutation = useMutation({
    mutationFn: (text: string) => conversationsAPI.sendMessage(id!, text),
    onSuccess: () => {
      setMessageText('')
      queryClient.invalidateQueries({ queryKey: ['conversation', id] })
    },
    onError: () => {
      message.error('Ошибка отправки сообщения')
    },
  })

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation?.messages?.length])

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!conversation) {
    return <Empty description="Диалог не найден" />
  }

  const config = statusConfig[conversation.status]

  const handleSendMessage = () => {
    const text = messageText.trim()
    if (text) {
      sendMessageMutation.mutate(text)
    }
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/conversations')}>
          Назад
        </Button>
      </Space>

      <div style={{ display: 'flex', gap: 24 }}>
        {/* Chat View */}
        <div style={{ flex: 1 }}>
          <Card
            title={
              <Space>
                <Typography.Text strong>Диалог</Typography.Text>
                <Tag color={config.color}>{config.label}</Tag>
              </Space>
            }
            extra={
              <Space>
                {conversation.status === 'active' && (
                  <>
                    <Button
                      icon={<PauseCircleOutlined />}
                      onClick={() => statusMutation.mutate('paused')}
                      loading={statusMutation.isPending}
                    >
                      Пауза
                    </Button>
                    <Button
                      icon={<SwapOutlined />}
                      onClick={() => statusMutation.mutate('handed_off')}
                      loading={statusMutation.isPending}
                    >
                      Передать
                    </Button>
                    <Button
                      icon={<CheckCircleOutlined />}
                      onClick={() => statusMutation.mutate('completed')}
                      loading={statusMutation.isPending}
                    >
                      Завершить
                    </Button>
                  </>
                )}
                {conversation.status === 'paused' && (
                  <Button
                    type="primary"
                    onClick={() => statusMutation.mutate('active')}
                    loading={statusMutation.isPending}
                  >
                    Возобновить
                  </Button>
                )}
                {conversation.status === 'handed_off' && (
                  <>
                    <Button
                      icon={<RobotOutlined />}
                      onClick={() => statusMutation.mutate('active')}
                      loading={statusMutation.isPending}
                    >
                      Вернуть боту
                    </Button>
                    <Button
                      icon={<CheckCircleOutlined />}
                      onClick={() => statusMutation.mutate('completed')}
                      loading={statusMutation.isPending}
                    >
                      Завершить
                    </Button>
                  </>
                )}
              </Space>
            }
          >
            <div
              style={{
                maxHeight: 600,
                overflowY: 'auto',
                padding: '8px 0',
              }}
            >
              {conversation.messages.length === 0 ? (
                <Empty description="Нет сообщений" />
              ) : (
                conversation.messages.map((msg) => (
                  <MessageBubble key={msg.id} msg={msg} />
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {conversation.status === 'handed_off' && (
              <div style={{ display: 'flex', gap: 8, marginTop: 12, borderTop: `1px solid ${token.colorBorderSecondary}`, paddingTop: 12 }}>
                <Input.TextArea
                  value={messageText}
                  onChange={(e) => setMessageText(e.target.value)}
                  placeholder="Введите сообщение..."
                  autoSize={{ minRows: 1, maxRows: 4 }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && messageText.trim()) {
                      e.preventDefault()
                      handleSendMessage()
                    }
                  }}
                />
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSendMessage}
                  loading={sendMessageMutation.isPending}
                  disabled={!messageText.trim()}
                >
                  Отправить
                </Button>
              </div>
            )}
          </Card>
        </div>

        {/* Sidebar */}
        <div style={{ width: 320 }}>
          <Card title="Информация">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Лид">
                {conversation.lead_name || conversation.lead_id.slice(0, 8) + '...'}
              </Descriptions.Item>
              <Descriptions.Item label="Канал">
                {conversation.channel_name || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Статус">
                <Tag color={config.color}>{config.label}</Tag>
              </Descriptions.Item>
              {conversation.manager_name && (
                <Descriptions.Item label="Менеджер">
                  {conversation.manager_name}
                </Descriptions.Item>
              )}
              <Descriptions.Item label="Сообщений">
                {conversation.message_count}
              </Descriptions.Item>
              <Descriptions.Item label="Начат">
                {conversation.started_at
                  ? dayjs(conversation.started_at).format('DD.MM.YYYY HH:mm')
                  : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Завершён">
                {conversation.ended_at
                  ? dayjs(conversation.ended_at).format('DD.MM.YYYY HH:mm')
                  : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Создан">
                {dayjs(conversation.created_at).format('DD.MM.YYYY HH:mm')}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </div>
      </div>
    </div>
  )
}
