import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Form, Input, Button, Typography, message, theme } from 'antd'
import { LockOutlined, MailOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/store/authStore'

const { Title } = Typography

interface LoginFormValues {
  email: string
  password: string
}

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const login = useAuthStore((state) => state.login)
  const { token: { colorBgLayout } } = theme.useToken()

  const onFinish = async (values: LoginFormValues) => {
    setLoading(true)
    try {
      await login(values.email, values.password)
      message.success('Вход выполнен')
      navigate('/dashboard')
    } catch {
      message.error('Неверный email или пароль')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: colorBgLayout,
      }}
    >
      <Card style={{ width: 400, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={3} style={{ margin: 0 }}>
            AI Lead Manager
          </Title>
          <Typography.Text type="secondary">
            Войдите в админ-панель
          </Typography.Text>
        </div>
        <Form
          name="login"
          onFinish={onFinish}
          layout="vertical"
          size="large"
        >
          <Form.Item
            name="email"
            tooltip="Введите email учётной записи администратора"
            rules={[
              { required: true, message: 'Введите email' },
              { type: 'email', message: 'Некорректный email' },
            ]}
          >
            <Input
              prefix={<MailOutlined />}
              placeholder="Email"
              autoComplete="email"
            />
          </Form.Item>
          <Form.Item
            name="password"
            tooltip="Введите пароль от вашей учётной записи"
            rules={[
              { required: true, message: 'Введите пароль' },
              { min: 6, message: 'Минимум 6 символов' },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="Пароль"
              autoComplete="current-password"
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              Войти
            </Button>
          </Form.Item>
        </Form>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <Typography.Link onClick={() => navigate('/register')}>
            Создать аккаунт
          </Typography.Link>
          <Typography.Link onClick={() => navigate('/')}>
            О сервисе
          </Typography.Link>
        </div>
      </Card>
    </div>
  )
}
