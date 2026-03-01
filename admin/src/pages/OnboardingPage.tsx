import { useNavigate } from 'react-router-dom'
import { Steps, Button, Typography, Card, Space, Row, Col, theme } from 'antd'
import {
  RocketOutlined,
  FileTextOutlined,
  QuestionCircleOutlined,
  ApiOutlined,
  SettingOutlined,
  CheckCircleOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/authStore'
import { useOnboardingStore } from '@/store/onboardingStore'

const { Title, Paragraph, Text } = Typography

interface OnboardingStep {
  key: string
  title: string
  icon: React.ReactNode
  description: string
  howItWorks: string
  actionLabel: string | null
  actionPath: string | null
}

const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    key: 'welcome',
    title: 'Добро пожаловать',
    icon: <RocketOutlined />,
    description:
      'AI Lead Manager — это система автоматической квалификации лидов с помощью искусственного интеллекта. AI-бот общается с потенциальными клиентами через Telegram или виджет на сайте, задаёт квалифицирующие вопросы и оценивает их готовность к покупке.',
    howItWorks:
      'Система работает в 4 шага: вы создаёте скрипт квалификации, добавляете базу знаний, подключаете канал связи и настраиваете AI. После этого бот начнёт автоматически обрабатывать входящие обращения и квалифицировать лидов по заданным критериям.',
    actionLabel: null,
    actionPath: null,
  },
  {
    key: 'script',
    title: 'Скрипт квалификации',
    icon: <FileTextOutlined />,
    description:
      'Скрипт квалификации определяет, какие вопросы AI-бот будет задавать лидам и как оценивать их ответы. Каждый скрипт состоит из этапов (стадий), по которым бот последовательно проводит клиента: выявление потребностей, проверка бюджета, сроков и лица, принимающего решение.',
    howItWorks:
      'Создайте скрипт вручную, задав этапы и веса оценки для каждого, или используйте AI-генерацию — просто опишите ваш продукт текстом, и система автоматически создаст скрипт с подходящими этапами квалификации. Каждому этапу назначается вес в баллах, и по мере прохождения этапов interest score лида растёт от 0 до 100.',
    actionLabel: 'Перейти к скриптам',
    actionPath: '/scripts',
  },
  {
    key: 'knowledge',
    title: 'База знаний',
    icon: <QuestionCircleOutlined />,
    description:
      'База знаний — это FAQ и типовые возражения, которые AI использует при ответах на вопросы клиентов. Чем полнее база знаний, тем точнее и полезнее ответы бота. Этот шаг необязателен, но значительно повышает качество диалогов.',
    howItWorks:
      'Добавьте часто задаваемые вопросы с ответами и типовые возражения с шаблонами ответов. Можно добавлять вручную или импортировать из текста — AI автоматически разберёт и структурирует данные. Записи можно привязать к конкретному скрипту квалификации или оставить глобальными.',
    actionLabel: 'Перейти к базе знаний',
    actionPath: '/scripts',
  },
  {
    key: 'channel',
    title: 'Канал связи',
    icon: <ApiOutlined />,
    description:
      'Канал связи — это способ, которым клиенты будут общаться с AI-ботом. Поддерживаются два типа: Telegram-бот и веб-виджет для встраивания на сайт. К каждому каналу можно привязать свой скрипт квалификации.',
    howItWorks:
      'Для Telegram: создайте бота через @BotFather в Telegram, скопируйте токен и укажите его при создании канала. Выберите режим работы — webhook или long polling. Для веб-виджета: создайте канал, скопируйте embed-код и вставьте его на ваш сайт. После активации канала бот начнёт принимать сообщения.',
    actionLabel: 'Перейти к каналам',
    actionPath: '/channels',
  },
  {
    key: 'settings',
    title: 'Настройки AI',
    icon: <SettingOutlined />,
    description:
      'Настройте AI-модель, которая будет вести диалоги с лидами. Укажите API-ключ провайдера (Anthropic, OpenAI или OpenRouter), выберите модель и задайте текст приветствия для новых клиентов.',
    howItWorks:
      'Выберите LLM-провайдера в разделе настроек, вставьте ваш API-ключ и настройте текст приветствия. Без API-ключа бот не сможет отвечать на сообщения. Рекомендуем начать с Anthropic Claude или OpenAI GPT-4o. Также можно настроить уведомления и интеграцию с CRM.',
    actionLabel: 'Перейти к настройкам',
    actionPath: '/settings',
  },
  {
    key: 'done',
    title: 'Готово!',
    icon: <CheckCircleOutlined />,
    description:
      'Вы знаете всё необходимое для настройки вашей первой воронки квалификации. Выполните шаги выше, и AI-бот начнёт автоматически обрабатывать лидов, квалифицировать их и передавать вам горячие контакты.',
    howItWorks:
      'После настройки все входящие обращения будут автоматически обрабатываться ботом. Статистику и результаты квалификации вы увидите на дашборде. Вы можете вернуться к этому руководству в любой момент через пункт «Обучение» в боковом меню.',
    actionLabel: 'Перейти на дашборд',
    actionPath: '/dashboard',
  },
]

export default function OnboardingPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { currentStep, setStep, nextStep, prevStep, completeOnboarding } = useOnboardingStore()

  const {
    token: { colorPrimary, colorFillAlter, colorBorderSecondary, borderRadiusLG },
  } = theme.useToken()

  const step = ONBOARDING_STEPS[currentStep]
  const isLastStep = currentStep === ONBOARDING_STEPS.length - 1
  const isFirstStep = currentStep === 0

  const handleAction = () => {
    if (isLastStep && user) {
      completeOnboarding(user.id)
    }
    if (step.actionPath) {
      navigate(step.actionPath)
    }
  }

  const handleSkip = () => {
    if (user) {
      completeOnboarding(user.id)
    }
    navigate('/dashboard')
  }

  return (
    <Row gutter={24} style={{ minHeight: 'calc(100vh - 200px)' }}>
      <Col xs={24} md={7} lg={6}>
        <Steps
          current={currentStep}
          direction="vertical"
          onChange={setStep}
          items={ONBOARDING_STEPS.map((s) => ({
            title: s.title,
            icon: s.icon,
          }))}
          style={{ position: 'sticky', top: 24 }}
        />
      </Col>

      <Col xs={24} md={17} lg={18}>
        <Card
          style={{ borderRadius: borderRadiusLG }}
          styles={{ body: { padding: '32px 40px' } }}
        >
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <div
              style={{
                fontSize: 56,
                color: colorPrimary,
                marginBottom: 16,
              }}
            >
              {step.icon}
            </div>
            <Title level={3} style={{ marginBottom: 0 }}>
              {step.title}
            </Title>
          </div>

          <Paragraph style={{ fontSize: 15, lineHeight: 1.8, maxWidth: 640, margin: '0 auto' }}>
            {step.description}
          </Paragraph>

          <Card
            size="small"
            style={{
              background: colorFillAlter,
              marginTop: 20,
              marginBottom: 28,
              maxWidth: 640,
              marginLeft: 'auto',
              marginRight: 'auto',
            }}
          >
            <Text strong>Как это работает:</Text>
            <br />
            <Text type="secondary" style={{ lineHeight: 1.7 }}>
              {step.howItWorks}
            </Text>
          </Card>

          {step.actionLabel && (
            <div style={{ textAlign: 'center', marginBottom: 24 }}>
              <Button
                type="primary"
                size="large"
                icon={<ArrowRightOutlined />}
                onClick={handleAction}
              >
                {step.actionLabel}
              </Button>
            </div>
          )}

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderTop: `1px solid ${colorBorderSecondary}`,
              paddingTop: 20,
            }}
          >
            <Button type="link" onClick={handleSkip} style={{ paddingLeft: 0 }}>
              Пропустить обучение
            </Button>
            <Space>
              {!isFirstStep && <Button onClick={prevStep}>Назад</Button>}
              {isLastStep ? (
                <Button type="primary" onClick={handleAction}>
                  Завершить
                </Button>
              ) : (
                <Button type="primary" onClick={nextStep}>
                  Далее
                </Button>
              )}
            </Space>
          </div>
        </Card>
      </Col>
    </Row>
  )
}
