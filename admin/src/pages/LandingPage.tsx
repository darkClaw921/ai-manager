import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from 'antd'
import { motion } from 'framer-motion'
import {
  RobotOutlined,
  MessageOutlined,
  FileTextOutlined,
  BarChartOutlined,
  CalendarOutlined,
  ApiOutlined,
  SunOutlined,
  MoonOutlined,
  CheckCircleFilled,
  UserOutlined,
  MailOutlined,
  PhoneOutlined,
  BankOutlined,
  SendOutlined,
  ClockCircleOutlined,
  RightOutlined,
} from '@ant-design/icons'
import { useThemeStore } from '@/store/themeStore'
import AnimatedSection from '@/components/landing/AnimatedSection'
import './landing.css'

const chatMessages = [
  { role: 'user' as const, text: 'Здравствуйте, интересует автоматизация продаж', delay: 0.6 },
  {
    role: 'ai' as const,
    text: 'Добрый день! Расскажите, сколько входящих заявок вы обрабатываете в месяц?',
    delay: 2.0,
  },
  { role: 'user' as const, text: 'Около 300, но менеджеры не успевают обработать все', delay: 3.8 },
  {
    role: 'ai' as const,
    text: 'Понял. С AI Lead Manager все 300 заявок будут квалифицированы автоматически. Какой бюджет вы рассматриваете?',
    delay: 5.6,
  },
]

const features = [
  {
    icon: <RobotOutlined />,
    title: 'AI-квалификация лидов',
    description:
      'Искусственный интеллект квалифицирует входящие заявки по вашим критериям и скриптам продаж. Автоматический скоринг от 0 до 100 и продвижение по воронке.',
  },
  {
    icon: <MessageOutlined />,
    title: 'Telegram-боты и веб-виджеты',
    description:
      'Подключите неограниченное количество Telegram-ботов и веб-виджетов. Все каналы в едином интерфейсе управления.',
  },
  {
    icon: <FileTextOutlined />,
    title: 'Скрипты продаж и FAQ',
    description:
      'Загружайте скрипты квалификации, базу знаний FAQ и обработку возражений. AI использует их в каждом диалоге с клиентом.',
  },
  {
    icon: <BarChartOutlined />,
    title: 'Аналитика продаж в реальном времени',
    description:
      'Дашборд с метриками: конверсии, качество лидов, активность по каналам, воронка продаж и экспорт данных в CSV и Google Sheets.',
  },
  {
    icon: <CalendarOutlined />,
    title: 'Автоматическая запись на консультации',
    description:
      'AI записывает квалифицированных лидов на консультации через встроенный календарь с учётом графика менеджеров.',
  },
  {
    icon: <ApiOutlined />,
    title: 'Интеграции с CRM и LLM',
    description:
      'Anthropic Claude, OpenAI, OpenRouter для AI. Google Sheets, CRM-вебхуки, Telegram-уведомления для бизнес-процессов.',
  },
]

const stats = [
  { value: '24/7', label: 'Обработка заявок без выходных' },
  { value: '<5 мин', label: 'Настройка и запуск' },
  { value: '100%', label: 'Заявок обработано' },
  { value: '3+', label: 'LLM-провайдера на выбор' },
]

const steps = [
  { title: 'Регистрация', description: 'Создайте аккаунт бесплатно и получите доступ к панели управления' },
  {
    title: 'Настройка каналов',
    description: 'Подключите Telegram-бота или установите веб-виджет чата на сайт',
  },
  {
    title: 'Загрузка скриптов продаж',
    description: 'Добавьте скрипты квалификации, FAQ и обработку возражений',
  },
  {
    title: 'Автоматическая квалификация',
    description: 'AI квалифицирует лидов, оценивает интерес и записывает на консультации',
  },
]

const testimonials = [
  {
    quote: 'Сократили время обработки входящих заявок в 4 раза. Менеджеры теперь работают только с горячими лидами.',
    name: 'Михаил Козлов',
    role: 'Директор по продажам',
    company: 'DigitalPro',
  },
  {
    quote: '300 заявок в месяц квалифицируются полностью без участия менеджеров. AI не пропускает ни одного лида.',
    name: 'Анна Семёнова',
    role: 'Руководитель отдела продаж',
    company: 'MarketHub',
  },
  {
    quote: 'ROI 320% за первые 3 месяца. Окупили внедрение за 2 недели благодаря автоматической квалификации.',
    name: 'Дмитрий Волков',
    role: 'Владелец бизнеса',
    company: 'TechStart',
  },
]

const faqItems = [
  {
    question: 'Что такое AI Lead Manager?',
    answer: 'AI Lead Manager — это AI-менеджер по продажам, который автоматически квалифицирует входящие заявки через Telegram-ботов и веб-виджеты. Система использует искусственный интеллект для ведения диалогов по вашим скриптам продаж, оценивает интерес клиентов и записывает квалифицированных лидов на консультации.',
  },
  {
    question: 'Как работает AI-квалификация лидов?',
    answer: 'AI ведёт диалог с клиентом по настроенным этапам квалификации: выявляет потребности, уточняет бюджет, сроки и лицо, принимающее решение. На каждом этапе система присваивает баллы и автоматически рассчитывает Interest Score от 0 до 100. Квалифицированные лиды передаются менеджерам.',
  },
  {
    question: 'Какие каналы для общения с клиентами поддерживаются?',
    answer: 'Telegram-боты (webhook и long-polling режимы) и веб-виджеты для сайтов. Можно подключить неограниченное количество каналов, каждый со своими скриптами квалификации.',
  },
  {
    question: 'Сколько стоит AI Lead Manager?',
    answer: 'Вы можете начать бесплатно. Оплачиваются только API-запросы к LLM-провайдерам (Anthropic Claude, OpenAI, OpenRouter) по их тарифам. Платформа сама не взимает абонентской платы.',
  },
  {
    question: 'Как быстро можно запустить AI-квалификацию?',
    answer: 'Настройка занимает менее 5 минут: зарегистрируйтесь, подключите Telegram-бота или веб-виджет, загрузите скрипты продаж — и AI начнёт обрабатывать заявки автоматически.',
  },
  {
    question: 'Безопасны ли данные клиентов?',
    answer: 'Да. Все данные хранятся в защищённой базе данных PostgreSQL. API-ключи шифруются. Доступ к панели управления защищён JWT-авторизацией. Каждый менеджер видит только свои данные.',
  },
]

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0 },
}

export default function LandingPage() {
  const navigate = useNavigate()
  const isDark = useThemeStore((s) => s.isDark)
  const toggleTheme = useThemeStore((s) => s.toggleTheme)
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  return (
    <div className={`landing${isDark ? '' : ' landing-light'}`}>
      {/* Background glow orbs */}
      <motion.div
        style={{
          position: 'absolute',
          width: 700,
          height: 700,
          borderRadius: '50%',
          background: isDark
            ? 'radial-gradient(circle, rgba(212, 168, 67, 0.07) 0%, transparent 70%)'
            : 'radial-gradient(circle, rgba(184, 146, 46, 0.04) 0%, transparent 70%)',
          top: '-5%',
          right: '-10%',
          filter: 'blur(80px)',
          pointerEvents: 'none',
          zIndex: 0,
        }}
        animate={{ x: [0, 30, -20, 0], y: [0, -25, 15, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        style={{
          position: 'absolute',
          width: 500,
          height: 500,
          borderRadius: '50%',
          background: isDark
            ? 'radial-gradient(circle, rgba(212, 168, 67, 0.05) 0%, transparent 70%)'
            : 'radial-gradient(circle, rgba(184, 146, 46, 0.03) 0%, transparent 70%)',
          bottom: '20%',
          left: '-5%',
          filter: 'blur(60px)',
          pointerEvents: 'none',
          zIndex: 0,
        }}
        animate={{ x: [0, -15, 20, 0], y: [0, 15, -10, 0] }}
        transition={{ duration: 13, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Navbar */}
      <nav className="landing-nav" aria-label="Главная навигация">
        <div className="landing-nav-inner">
          <a href="/" className="landing-nav-logo" aria-label="AI Lead Manager — главная">
            AI<span>.</span>Lead Manager
          </a>
          <div className="landing-nav-actions">
            <button
              className="landing-theme-toggle"
              onClick={toggleTheme}
              aria-label={isDark ? 'Включить светлую тему' : 'Включить тёмную тему'}
            >
              {isDark ? <SunOutlined /> : <MoonOutlined />}
            </button>
            <Button
              type="text"
              size="middle"
              onClick={() => navigate('/login')}
              style={{
                color: 'var(--text-dim)',
                fontFamily: "'Outfit', sans-serif",
                fontWeight: 500,
                fontSize: 14,
              }}
            >
              Войти
            </Button>
            <Button
              size="middle"
              onClick={() => navigate('/register')}
              style={{
                background: 'var(--accent-glow)',
                border: '1px solid var(--border-accent)',
                color: 'var(--accent)',
                fontFamily: "'Outfit', sans-serif",
                fontWeight: 600,
                fontSize: 14,
                borderRadius: 10,
                height: 36,
                paddingInline: 20,
              }}
            >
              Начать бесплатно
            </Button>
          </div>
        </div>
      </nav>

      <main>
        {/* Hero */}
        <section className="landing-hero" aria-label="AI Lead Manager — автоматизация квалификации лидов">
          <div className="landing-hero-inner">
            <div className="landing-hero-content">
              <motion.div {...fadeUp} transition={{ duration: 0.7, delay: 0.1 }}>
                <div className="landing-hero-badge">AI-менеджер по продажам</div>
              </motion.div>

              <motion.h1
                className="landing-hero-title"
                {...fadeUp}
                transition={{ duration: 0.7, delay: 0.2 }}
              >
                AI-менеджер квалифицирует
                <br />
                лидов на <em>автопилоте</em>
              </motion.h1>

              <motion.p
                className="landing-hero-subtitle"
                {...fadeUp}
                transition={{ duration: 0.7, delay: 0.35 }}
              >
                Автоматизация первичных продаж: AI обрабатывает входящие заявки 24/7 через Telegram и
                веб-виджет, квалифицирует клиентов и записывает на консультации.
              </motion.p>

              <motion.div
                className="landing-hero-ctas"
                {...fadeUp}
                transition={{ duration: 0.7, delay: 0.5 }}
              >
                <Button
                  size="large"
                  onClick={() => navigate('/register')}
                  aria-label="Зарегистрироваться бесплатно"
                  style={{
                    height: 52,
                    paddingInline: 36,
                    fontSize: 16,
                    fontWeight: 600,
                    background: isDark
                      ? 'linear-gradient(135deg, #D4A843, #C4783D)'
                      : 'linear-gradient(135deg, #B8922E, #A06E28)',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 12,
                    fontFamily: "'Outfit', sans-serif",
                    boxShadow: isDark
                      ? '0 4px 24px rgba(212, 168, 67, 0.25)'
                      : '0 4px 24px rgba(184, 146, 46, 0.2)',
                  }}
                >
                  Начать бесплатно
                </Button>
                <Button
                  size="large"
                  onClick={() => navigate('/login')}
                  style={{
                    height: 52,
                    paddingInline: 32,
                    fontSize: 16,
                    fontWeight: 500,
                    background: 'transparent',
                    color: 'var(--text-dim)',
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    fontFamily: "'Outfit', sans-serif",
                  }}
                >
                  Войти в систему
                </Button>
              </motion.div>
              <motion.p
                className="landing-hero-trust"
                {...fadeUp}
                transition={{ duration: 0.7, delay: 0.65 }}
              >
                Бесплатно. Без карты. Настройка за 5 минут.
              </motion.p>
            </div>

            {/* Chat Mockup */}
            <motion.div
              initial={{ opacity: 0, y: 40, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.9, delay: 0.4, ease: 'easeOut' }}
              aria-hidden="true"
            >
              <div className="landing-chat">
                <div className="landing-chat-header">
                  <div className="landing-chat-avatar">AI</div>
                  <div className="landing-chat-info">
                    <h4>AI Lead Manager</h4>
                    <span>Онлайн</span>
                  </div>
                </div>
                <div className="landing-chat-messages">
                  {chatMessages.map((msg, i) => (
                    <motion.div
                      key={i}
                      className={`landing-chat-msg ${msg.role}`}
                      initial={{ opacity: 0, y: 8, scale: 0.97 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{
                        delay: msg.delay,
                        duration: 0.35,
                        ease: 'easeOut',
                      }}
                    >
                      {msg.text}
                    </motion.div>
                  ))}
                  <motion.div
                    className="landing-chat-typing"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 7.2 }}
                  >
                    <span />
                    <span />
                    <span />
                  </motion.div>
                </div>
              </div>
            </motion.div>
          </div>
        </section>

        {/* Stats */}
        <section className="landing-stats" aria-label="Ключевые показатели">
          <div className="landing-stats-inner">
            {stats.map((stat, i) => (
              <AnimatedSection key={stat.label} delay={i * 0.1}>
                <div className="landing-stat">
                  <div className="landing-stat-value">{stat.value}</div>
                  <div className="landing-stat-label">{stat.label}</div>
                </div>
              </AnimatedSection>
            ))}
          </div>
        </section>

        {/* Testimonials */}
        <section className="landing-testimonials" aria-label="Отзывы клиентов">
          <div className="landing-testimonials-inner">
            <AnimatedSection>
              <div style={{ textAlign: 'center', marginBottom: 64 }}>
                <div className="landing-section-label" style={{ justifyContent: 'center' }}>
                  Отзывы
                </div>
                <h2 className="landing-section-title" style={{ margin: '0 auto 14px' }}>
                  Результаты наших клиентов
                </h2>
                <p
                  className="landing-section-subtitle"
                  style={{ margin: '0 auto', textAlign: 'center' }}
                >
                  Компании автоматизируют продажи и получают больше квалифицированных лидов
                </p>
              </div>
            </AnimatedSection>

            <div className="landing-testimonials-grid">
              {testimonials.map((t, i) => (
                <AnimatedSection key={t.name} delay={i * 0.1}>
                  <blockquote className="landing-testimonial-card">
                    <div className="landing-testimonial-quote">&ldquo;</div>
                    <p>{t.quote}</p>
                    <footer className="landing-testimonial-author">
                      <div className="landing-testimonial-avatar">
                        {t.name[0]}
                      </div>
                      <div>
                        <cite className="landing-testimonial-name">{t.name}</cite>
                        <div className="landing-testimonial-role">
                          {t.role}, {t.company}
                        </div>
                      </div>
                    </footer>
                  </blockquote>
                </AnimatedSection>
              ))}
            </div>
          </div>
        </section>

        {/* Features */}
        <section className="landing-features" aria-label="Возможности платформы">
          <AnimatedSection>
            <div className="landing-section-label">Возможности</div>
            <h2 className="landing-section-title">
              Полная автоматизация
              <br />
              первичных продаж
            </h2>
            <p className="landing-section-subtitle">
              Всё что нужно для автоматической квалификации лидов: от AI-скриптов до аналитики и записи на
              консультации
            </p>
          </AnimatedSection>

          <div className="landing-features-grid">
            {features.map((feature, i) => (
              <AnimatedSection key={feature.title} delay={i * 0.08}>
                <article className="landing-feature-card">
                  <div className="landing-feature-icon">{feature.icon}</div>
                  <h3>{feature.title}</h3>
                  <p>{feature.description}</p>
                </article>
              </AnimatedSection>
            ))}
          </div>
        </section>

        {/* How It Works */}
        <section className="landing-how" aria-label="Как начать работу">
          <div className="landing-how-inner">
            <AnimatedSection>
              <div style={{ textAlign: 'center', marginBottom: 64 }}>
                <div className="landing-section-label" style={{ justifyContent: 'center' }}>
                  Как это работает
                </div>
                <h2 className="landing-section-title" style={{ margin: '0 auto 14px' }}>
                  Четыре шага до автоматических продаж
                </h2>
                <p
                  className="landing-section-subtitle"
                  style={{ margin: '0 auto', textAlign: 'center' }}
                >
                  От регистрации до первых квалифицированных лидов — менее чем за один день
                </p>
              </div>
            </AnimatedSection>

            <div className="landing-how-steps">
              {steps.map((step, i) => (
                <AnimatedSection key={step.title} delay={i * 0.12}>
                  <div className="landing-how-step">
                    <div className="landing-how-num">{i + 1}</div>
                    <h3>{step.title}</h3>
                    <p>{step.description}</p>
                  </div>
                </AnimatedSection>
              ))}
            </div>
          </div>
        </section>

        {/* Lead Preview */}
        <section className="landing-lead-preview" aria-label="Пример квалифицированного лида">
          <div className="landing-lead-preview-inner">
            <AnimatedSection>
              <div style={{ textAlign: 'center', marginBottom: 64 }}>
                <div className="landing-section-label" style={{ justifyContent: 'center' }}>
                  Результат квалификации
                </div>
                <h2 className="landing-section-title" style={{ margin: '0 auto 14px' }}>
                  Карточка квалифицированного
                  <br />
                  лида в панели управления
                </h2>
                <p
                  className="landing-section-subtitle"
                  style={{ margin: '0 auto', textAlign: 'center' }}
                >
                  Полная информация о клиенте, прогресс квалификации и оценка интереса — всё в
                  одном месте
                </p>
              </div>
            </AnimatedSection>

            <AnimatedSection delay={0.15}>
              <div className="landing-lead-card" aria-hidden="true">
                {/* Header */}
                <div className="landing-lead-header">
                  <div className="landing-lead-avatar">
                    <UserOutlined />
                  </div>
                  <div className="landing-lead-header-info">
                    <h3>Алексей Петров</h3>
                    <span className="landing-lead-tag qualified">Квалифицирован</span>
                  </div>
                  <div className="landing-lead-score">
                    <div className="landing-lead-score-value">85</div>
                    <div className="landing-lead-score-label">Interest Score</div>
                  </div>
                </div>

                {/* Body — two columns */}
                <div className="landing-lead-body">
                  {/* Left: contact info + meta */}
                  <div className="landing-lead-info">
                    <div className="landing-lead-info-title">Контактные данные</div>
                    <div className="landing-lead-info-rows">
                      <div className="landing-lead-info-row">
                        <MailOutlined />
                        <span>a.petrov@company.ru</span>
                      </div>
                      <div className="landing-lead-info-row">
                        <PhoneOutlined />
                        <span>+7 (999) 123-45-67</span>
                      </div>
                      <div className="landing-lead-info-row">
                        <BankOutlined />
                        <span>ООО «ТехноСтарт»</span>
                      </div>
                      <div className="landing-lead-info-row">
                        <SendOutlined />
                        <span>Telegram</span>
                      </div>
                      <div className="landing-lead-info-row">
                        <ClockCircleOutlined />
                        <span>Сегодня, 14:32</span>
                      </div>
                    </div>

                    {/* Score bar */}
                    <div className="landing-lead-bar-section">
                      <div className="landing-lead-bar-header">
                        <span>Оценка интереса</span>
                        <span className="landing-lead-bar-pct">85%</span>
                      </div>
                      <div className="landing-lead-bar-track">
                        <motion.div
                          className="landing-lead-bar-fill"
                          initial={{ width: 0 }}
                          whileInView={{ width: '85%' }}
                          transition={{ duration: 1.2, delay: 0.5, ease: 'easeOut' }}
                          viewport={{ once: true }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Right: qualification stages */}
                  <div className="landing-lead-stages">
                    <div className="landing-lead-info-title">Этапы квалификации</div>
                    <div className="landing-lead-stages-list">
                      {[
                        {
                          label: 'Выявление потребностей',
                          weight: 25,
                          done: true,
                          info: 'Автоматизация обработки 300 заявок/мес',
                        },
                        {
                          label: 'Проверка бюджета',
                          weight: 25,
                          done: true,
                          info: 'Бюджет: 200–300 тыс. руб./мес',
                        },
                        {
                          label: 'Сроки внедрения',
                          weight: 25,
                          done: true,
                          info: 'Запуск нужен в течение 2 недель',
                        },
                        {
                          label: 'Лицо принимающее решение',
                          weight: 10,
                          done: true,
                          info: 'Директор по продажам, имеет полномочия',
                        },
                      ].map((stage, i) => (
                        <motion.div
                          key={stage.label}
                          className={`landing-lead-stage ${stage.done ? 'done' : ''}`}
                          initial={{ opacity: 0, x: 12 }}
                          whileInView={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.4 + i * 0.12, duration: 0.35 }}
                          viewport={{ once: true }}
                        >
                          <div className="landing-lead-stage-header">
                            <CheckCircleFilled className="landing-lead-stage-check" />
                            <span className="landing-lead-stage-label">{stage.label}</span>
                            <span className="landing-lead-stage-weight">{stage.weight}%</span>
                          </div>
                          <div className="landing-lead-stage-info">{stage.info}</div>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </AnimatedSection>
          </div>
        </section>

        {/* FAQ */}
        <section className="landing-faq" aria-label="Часто задаваемые вопросы">
          <div className="landing-faq-inner">
            <AnimatedSection>
              <div style={{ textAlign: 'center', marginBottom: 64 }}>
                <div className="landing-section-label" style={{ justifyContent: 'center' }}>
                  Вопросы и ответы
                </div>
                <h2 className="landing-section-title" style={{ margin: '0 auto 14px' }}>
                  Частые вопросы об AI Lead Manager
                </h2>
                <p
                  className="landing-section-subtitle"
                  style={{ margin: '0 auto', textAlign: 'center' }}
                >
                  Ответы на популярные вопросы о платформе автоматической квалификации лидов
                </p>
              </div>
            </AnimatedSection>

            <div className="landing-faq-list">
              {faqItems.map((item, i) => (
                <AnimatedSection key={i} delay={i * 0.06}>
                  <div
                    className={`landing-faq-item${openFaq === i ? ' open' : ''}`}
                    onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  >
                    <button
                      className="landing-faq-question"
                      aria-expanded={openFaq === i}
                      aria-controls={`faq-answer-${i}`}
                    >
                      <h3>{item.question}</h3>
                      <RightOutlined className="landing-faq-arrow" />
                    </button>
                    <div
                      id={`faq-answer-${i}`}
                      className="landing-faq-answer"
                      role="region"
                    >
                      <p>{item.answer}</p>
                    </div>
                  </div>
                </AnimatedSection>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="landing-cta" aria-label="Начать использование">
          {/* CTA background glow */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: isDark
                ? 'radial-gradient(ellipse at 30% 50%, rgba(212, 168, 67, 0.05) 0%, transparent 50%), radial-gradient(ellipse at 70% 50%, rgba(196, 120, 61, 0.03) 0%, transparent 50%)'
                : 'radial-gradient(ellipse at 30% 50%, rgba(184, 146, 46, 0.03) 0%, transparent 50%), radial-gradient(ellipse at 70% 50%, rgba(160, 110, 40, 0.02) 0%, transparent 50%)',
              pointerEvents: 'none',
            }}
          />
          <AnimatedSection>
            <div className="landing-cta-inner">
              <h2>
                Готовы автоматизировать
                <br />
                квалификацию лидов?
              </h2>
              <p>
                Запустите AI Lead Manager за 5 минут и получайте только квалифицированных клиентов.
              </p>
              <Button
                size="large"
                onClick={() => navigate('/register')}
                aria-label="Зарегистрироваться и начать бесплатно"
                style={{
                  height: 56,
                  paddingInline: 48,
                  fontSize: 17,
                  fontWeight: 600,
                  background: isDark
                    ? 'linear-gradient(135deg, #D4A843, #C4783D)'
                    : 'linear-gradient(135deg, #B8922E, #A06E28)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 14,
                  fontFamily: "'Outfit', sans-serif",
                  boxShadow: isDark
                    ? '0 4px 32px rgba(212, 168, 67, 0.3)'
                    : '0 4px 32px rgba(184, 146, 46, 0.2)',
                }}
              >
                Начать бесплатно
              </Button>
              <p className="landing-cta-trust">
                Бесплатно. Без привязки карты. Настройка за 5 минут.
              </p>
            </div>
          </AnimatedSection>
        </section>
      </main>

      {/* Footer */}
      <footer className="landing-footer" aria-label="Подвал сайта">
        <div className="landing-footer-inner">
          <a href="/" className="landing-footer-logo" aria-label="AI Lead Manager — главная">
            AI<span>.</span>Lead Manager
          </a>
          <nav className="landing-footer-links" aria-label="Ссылки подвала">
            <a href="/register">Регистрация</a>
            <a href="/login">Вход</a>
          </nav>
        </div>
        <div className="landing-footer-bottom">
          &copy; 2026 AI Lead Manager. Автоматическая квалификация лидов через AI. Все права защищены.
        </div>
      </footer>
    </div>
  )
}
