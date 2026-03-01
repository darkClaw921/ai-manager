import { useState, useEffect } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Layout, Menu, Dropdown, Button, theme, type MenuProps } from 'antd'
import {
  DashboardOutlined,
  TeamOutlined,
  MessageOutlined,
  FileTextOutlined,
  ApiOutlined,
  CalendarOutlined,
  SettingOutlined,
  UserOutlined,
  UsergroupAddOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  SunOutlined,
  MoonOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/authStore'
import { useThemeStore } from '@/store/themeStore'
import { useImpersonationStore } from '@/store/impersonationStore'
import { useOnboardingStore } from '@/store/onboardingStore'
import ImpersonationBanner from '@/components/ImpersonationBanner'

const { Header, Sider, Content } = Layout

interface MenuItem {
  key: string
  icon: React.ReactNode
  label: string
  adminOnly?: boolean
  managerOnly?: boolean
}

const menuItems: MenuItem[] = [
  {
    key: '/dashboard',
    icon: <DashboardOutlined />,
    label: 'Дашборд',
  },
  {
    key: '/onboarding',
    icon: <RocketOutlined />,
    label: 'Обучение',
    managerOnly: true,
  },
  {
    key: '/leads',
    icon: <TeamOutlined />,
    label: 'Лиды',
  },
  {
    key: '/conversations',
    icon: <MessageOutlined />,
    label: 'Диалоги',
  },
  {
    key: '/scripts',
    icon: <FileTextOutlined />,
    label: 'Скрипты',
  },
  {
    key: '/channels',
    icon: <ApiOutlined />,
    label: 'Каналы',
  },
  {
    key: '/bookings',
    icon: <CalendarOutlined />,
    label: 'Записи',
  },
  {
    key: '/settings',
    icon: <SettingOutlined />,
    label: 'Настройки',
  },
  {
    key: '/users',
    icon: <UserOutlined />,
    label: 'Пользователи',
    adminOnly: true,
  },
  {
    key: '/managers',
    icon: <UsergroupAddOutlined />,
    label: 'Менеджеры',
    adminOnly: true,
  },
]

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const { isDark, toggleTheme } = useThemeStore()
  const { isImpersonating } = useImpersonationStore()
  const { isCompleted } = useOnboardingStore()
  const { token: { colorBgContainer, borderRadiusLG, colorTextLightSolid, colorText } } = theme.useToken()

  // Auto-redirect new managers to onboarding on first visit
  useEffect(() => {
    if (
      user &&
      user.role === 'manager' &&
      !isImpersonating &&
      !isCompleted(user.id) &&
      location.pathname === '/dashboard'
    ) {
      navigate('/onboarding', { replace: true })
    }
  }, [user?.id, location.pathname])

  const handleMenuClick: MenuProps['onClick'] = (e) => {
    navigate(e.key)
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'role',
      label: user?.role === 'admin' ? 'Администратор' : 'Менеджер',
      disabled: true,
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Выйти',
      onClick: handleLogout,
    },
  ]

  // Admin sees all items; during impersonation admin-only items are hidden
  const isAdmin = user?.role === 'admin' && !isImpersonating
  const isManager = user?.role === 'manager' || isImpersonating
  const filteredMenuItems: MenuProps['items'] = menuItems
    .filter((item) => {
      if (item.adminOnly && !isAdmin) return false
      if (item.managerOnly && !isManager) return false
      return true
    })
    .map(({ adminOnly: _, managerOnly: _m, ...rest }) => rest)

  // Determine selected key from current path
  const selectedKey = '/' + location.pathname.split('/')[1]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        breakpoint="lg"
        onBreakpoint={(broken) => {
          if (broken) {
            setCollapsed(true)
          }
        }}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: isDark ? colorText : colorTextLightSolid,
            fontSize: collapsed ? 14 : 16,
            fontWeight: 600,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
          }}
        >
          {collapsed ? 'AI' : 'AI Lead Manager'}
        </div>
        <Menu
          theme={isDark ? undefined : 'dark'}
          mode="inline"
          selectedKeys={[selectedKey]}
          items={filteredMenuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 200, transition: 'all 0.2s' }}>
        <ImpersonationBanner />
        <Header
          style={{
            padding: '0 24px',
            background: colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: 16, width: 64, height: 64 }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Button
              type="text"
              icon={isDark ? <SunOutlined /> : <MoonOutlined />}
              onClick={toggleTheme}
              style={{ fontSize: 16 }}
            />
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Button type="text" icon={<UserOutlined />}>
                {user?.full_name || user?.email || 'User'}
              </Button>
            </Dropdown>
          </div>
        </Header>
        <Content
          style={{
            margin: '24px 16px',
            padding: 24,
            minHeight: 280,
            background: colorBgContainer,
            borderRadius: borderRadiusLG,
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
