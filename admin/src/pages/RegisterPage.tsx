import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Form, Input, Button, Typography, message, theme } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons'
import { authAPI } from '@/api'
import { useAuthStore } from '@/store/authStore'

const { Title } = Typography

interface RegisterFormValues {
  full_name: string
  email: string
  password: string
  confirm_password: string
}

export default function RegisterPage() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const [form] = Form.useForm<RegisterFormValues>()
  const { token: { colorBgLayout } } = theme.useToken()

  const onFinish = async (values: RegisterFormValues) => {
    setLoading(true)
    try {
      const response = await authAPI.register({
        email: values.email,
        password: values.password,
        full_name: values.full_name,
      })

      const { access_token, refresh_token, user } = response.data

      // Save tokens and user data to auth store
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', refresh_token)
      useAuthStore.setState({
        token: access_token,
        refreshToken: refresh_token,
        user,
        isAuthenticated: true,
      })

      message.success('Регистрация успешна')
      navigate('/dashboard')
    } catch (err: unknown) {
      const error = err as { response?: { status?: number; data?: { detail?: string } } }
      if (error.response?.status === 409) {
        message.error('Email уже зарегистрирован')
      } else {
        message.error(error.response?.data?.detail || 'Ошибка регистрации')
      }
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
            Создайте аккаунт
          </Typography.Text>
        </div>
        <Form
          form={form}
          name="register"
          onFinish={onFinish}
          layout="vertical"
          size="large"
        >
          <Form.Item
            name="full_name"
            rules={[{ required: true, message: 'Введите имя' }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="Полное имя"
              autoComplete="name"
            />
          </Form.Item>
          <Form.Item
            name="email"
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
            rules={[
              { required: true, message: 'Введите пароль' },
              { min: 6, message: 'Минимум 6 символов' },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="Пароль"
              autoComplete="new-password"
            />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            dependencies={['password']}
            rules={[
              { required: true, message: 'Подтвердите пароль' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('Пароли не совпадают'))
                },
              }),
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="Подтвердите пароль"
              autoComplete="new-password"
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              Зарегистрироваться
            </Button>
          </Form.Item>
        </Form>
        <div style={{ textAlign: 'center' }}>
          <Typography.Link onClick={() => navigate('/login')}>
            Уже есть аккаунт? Войти
          </Typography.Link>
        </div>
      </Card>
    </div>
  )
}
