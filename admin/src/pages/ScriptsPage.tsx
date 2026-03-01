import { useState } from 'react'
import {
  Tabs,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Switch,
  InputNumber,
  Tag,
  Space,
  Popconfirm,
  Typography,
  Card,
  Collapse,
  Select,
  Segmented,
  Divider,
  message,
} from 'antd'
import {
  PlusOutlined,
  SyncOutlined,
  EditOutlined,
  DeleteOutlined,
  UploadOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  RobotOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { scriptsAPI } from '@/api'
import type { QualificationScript, FAQItem, ObjectionScript } from '@/types'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'

const { TextArea } = Input

// --- Qualification Scripts Tab ---

function QualificationTab() {
  const queryClient = useQueryClient()
  const [editingScript, setEditingScript] = useState<QualificationScript | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [editMode, setEditMode] = useState<'visual' | 'json'>('visual')
  const [form] = Form.useForm()
  const [generateModalOpen, setGenerateModalOpen] = useState(false)
  const [generateText, setGenerateText] = useState('')

  const generateMutation = useMutation({
    mutationFn: (text: string) => scriptsAPI.generateScript(text),
    onSuccess: (res) => {
      const script = res.data
      if (!script.stages || script.stages.length === 0) {
        message.warning('AI сгенерировал скрипт без этапов. Попробуйте уточнить описание.')
      } else {
        message.success(`Скрипт сгенерирован: ${script.name} (${script.stages.length} этапов)`)
      }
      queryClient.invalidateQueries({ queryKey: ['qualificationScripts'] })
      setGenerateModalOpen(false)
      setGenerateText('')
    },
    onError: (err: unknown) => {
      const axiosErr = err as { code?: string; message?: string; response?: { status?: number; data?: { detail?: string | unknown[] } } }
      if (axiosErr.code === 'ECONNABORTED') {
        message.error('Превышено время ожидания. Попробуйте ещё раз.')
      } else if (axiosErr.response?.data?.detail) {
        const detail = axiosErr.response.data.detail
        message.error(typeof detail === 'string' ? detail : 'Ошибка генерации.')
      } else {
        message.error(`Ошибка генерации (${axiosErr.response?.status ?? 'network'}): ${axiosErr.message || 'неизвестная ошибка'}`)
      }
    },
  })

  const { data: scripts, isLoading } = useQuery({
    queryKey: ['qualificationScripts'],
    queryFn: () => scriptsAPI.getScripts().then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (data: Partial<QualificationScript>) => scriptsAPI.createScript(data),
    onSuccess: () => {
      message.success('Скрипт создан')
      queryClient.invalidateQueries({ queryKey: ['qualificationScripts'] })
      setModalOpen(false)
      form.resetFields()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<QualificationScript> }) =>
      scriptsAPI.updateScript(id, data),
    onSuccess: () => {
      message.success('Скрипт обновлен')
      queryClient.invalidateQueries({ queryKey: ['qualificationScripts'] })
      setModalOpen(false)
      setEditingScript(null)
      form.resetFields()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => scriptsAPI.deleteScript(id),
    onSuccess: () => {
      message.success('Скрипт удален')
      queryClient.invalidateQueries({ queryKey: ['qualificationScripts'] })
    },
  })

  const [scoreWeights, setScoreWeights] = useState<Record<string, Record<string, number>>>({})

  const updateScoreConfigMutation = useMutation({
    mutationFn: ({ scriptId, config }: { scriptId: string; config: Record<string, number> }) =>
      scriptsAPI.updateScoreConfig(scriptId, config),
    onSuccess: () => {
      message.success('Веса обновлены')
      queryClient.invalidateQueries({ queryKey: ['qualificationScripts'] })
    },
    onError: (err: unknown) => {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      message.error(axiosErr.response?.data?.detail || 'Ошибка сохранения весов')
    },
  })

  const getScoreWeightsForScript = (script: QualificationScript): Record<string, number> => {
    if (scoreWeights[script.id]) return scoreWeights[script.id]
    if (script.score_config) return script.score_config
    // Default: 25 for each stage
    return Object.fromEntries(
      (script.stages || []).map((s) => [(s as Record<string, unknown>).stage_id as string, 25])
    )
  }

  const setScoreWeight = (scriptId: string, stageId: string, value: number) => {
    setScoreWeights((prev) => ({
      ...prev,
      [scriptId]: {
        ...getScoreWeightsForScript((scripts || []).find((s) => s.id === scriptId)!),
        ...prev[scriptId],
        [stageId]: value,
      },
    }))
  }

  const openCreate = () => {
    setEditingScript(null)
    form.resetFields()
    setEditMode('visual')
    setModalOpen(true)
  }

  const openEdit = (script: QualificationScript) => {
    setEditingScript(script)
    const stagesForVisual = (script.stages || []).map((s) => ({
      ...(s as Record<string, unknown>),
      follow_ups: Array.isArray((s as Record<string, unknown>).follow_ups)
        ? ((s as Record<string, unknown>).follow_ups as string[]).join(', ')
        : ((s as Record<string, unknown>).follow_ups || ''),
    }))
    form.setFieldsValue({
      name: script.name,
      description: script.description,
      stages: stagesForVisual,
      stages_json: JSON.stringify(script.stages, null, 2),
      is_active: script.is_active,
      score_config: script.score_config,
    })
    setModalOpen(true)
  }

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      let stages: Record<string, unknown>[] = []
      if (editMode === 'visual') {
        const raw = (values.stages || []) as Record<string, unknown>[]
        stages = raw.map((s, i) => ({
          ...s,
          follow_ups: typeof s.follow_ups === 'string' && s.follow_ups
            ? (s.follow_ups as string).split(',').map((f: string) => f.trim()).filter(Boolean)
            : [],
          order: i,
        }))
      } else {
        try {
          stages = JSON.parse(values.stages_json || '[]')
        } catch {
          message.error('Некорректный JSON этапов')
          return
        }
      }

      // Build score_config from form values if in visual mode
      let scoreConfig: Record<string, number> | null = null
      if (editMode === 'visual' && values.score_config) {
        scoreConfig = values.score_config
      } else if (editMode === 'visual') {
        // Try to derive from stages if user filled in weights
        const stageIds = stages
          .map((s) => s.stage_id as string)
          .filter(Boolean)
        if (stageIds.length > 0 && form.getFieldValue('score_config')) {
          scoreConfig = form.getFieldValue('score_config') as Record<string, number>
        }
      }

      const data = {
        name: values.name,
        description: values.description,
        stages,
        is_active: values.is_active ?? true,
        ...(scoreConfig ? { score_config: scoreConfig } : {}),
      }

      if (editingScript) {
        updateMutation.mutate({ id: editingScript.id, data })
      } else {
        createMutation.mutate(data)
      }
    })
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Добавить скрипт
        </Button>
        <Button icon={<RobotOutlined />} onClick={() => setGenerateModalOpen(true)}>
          Сгенерировать через AI
        </Button>
      </Space>

      {isLoading ? (
        <Typography.Text>Загрузка...</Typography.Text>
      ) : (
        <Collapse>
          {(scripts || []).map((script) => (
            <Collapse.Panel
              key={script.id}
              header={
                <Space>
                  <Typography.Text strong>{script.name}</Typography.Text>
                  {script.is_active && <Tag color="green">Активен</Tag>}
                </Space>
              }
              extra={
                <Space onClick={(e) => e.stopPropagation()}>
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(script)}>
                    Ред.
                  </Button>
                  <Popconfirm title="Удалить скрипт?" onConfirm={() => deleteMutation.mutate(script.id)}>
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              }
            >
              <Typography.Paragraph type="secondary">{script.description || 'Без описания'}</Typography.Paragraph>
              {script.stages && script.stages.length > 0 ? (
                <div>
                  {script.stages.map((stage, idx) => (
                    <Card key={idx} size="small" style={{ marginBottom: 8 }}>
                      <Typography.Text strong>
                        {idx + 1}. {(stage as Record<string, unknown>).stage_id as string || `Этап ${idx + 1}`}
                      </Typography.Text>
                      <br />
                      <Typography.Text type="secondary">
                        {(stage as Record<string, unknown>).question_prompt as string || ''}
                      </Typography.Text>
                    </Card>
                  ))}

                  <Divider />
                  <Typography.Title level={5}>Оценка интереса</Typography.Title>
                  <Typography.Paragraph type="secondary">
                    Укажите вес каждого этапа (в процентах) для расчёта interest score.
                  </Typography.Paragraph>
                  {script.stages.map((stage) => {
                    const stageId = (stage as Record<string, unknown>).stage_id as string
                    if (!stageId) return null
                    const weights = getScoreWeightsForScript(script)
                    return (
                      <Space key={stageId} style={{ marginBottom: 8, display: 'flex' }}>
                        <Typography.Text style={{ width: 180, display: 'inline-block' }}>{stageId}</Typography.Text>
                        <InputNumber
                          min={0}
                          max={100}
                          step={5}
                          value={weights[stageId] ?? 25}
                          onChange={(val) => setScoreWeight(script.id, stageId, val ?? 0)}
                        />
                        <Typography.Text>%</Typography.Text>
                      </Space>
                    )
                  })}
                  <div style={{ marginTop: 12 }}>
                    <Button
                      type="primary"
                      icon={<SaveOutlined />}
                      loading={updateScoreConfigMutation.isPending}
                      onClick={() => {
                        const weights = scoreWeights[script.id] || getScoreWeightsForScript(script)
                        updateScoreConfigMutation.mutate({ scriptId: script.id, config: weights })
                      }}
                    >
                      Сохранить веса
                    </Button>
                  </div>
                </div>
              ) : (
                <Typography.Text type="secondary">Нет этапов</Typography.Text>
              )}
            </Collapse.Panel>
          ))}
        </Collapse>
      )}

      <Modal
        title="Генерация скрипта через AI"
        open={generateModalOpen}
        onOk={() => generateMutation.mutate(generateText)}
        onCancel={() => { setGenerateModalOpen(false); setGenerateText('') }}
        confirmLoading={generateMutation.isPending}
        okText="Сгенерировать"
        okButtonProps={{ disabled: generateText.trim().length < 10 }}
      >
        <Typography.Paragraph type="secondary">
          Опишите ваш бизнес, продукт/услугу и кого нужно квалифицировать. AI создаст скрипт квалификации с этапами.
        </Typography.Paragraph>
        <TextArea
          rows={8}
          value={generateText}
          onChange={(e) => setGenerateText(e.target.value)}
          placeholder="Например: Мы продаём CRM-систему для малого бизнеса. Нужно квалифицировать владельцев бизнеса и руководителей отделов продаж, чтобы понять их текущие проблемы с управлением клиентами, бюджет на внедрение и сроки принятия решения."
        />
      </Modal>

      <Modal
        title={editingScript ? 'Редактировать скрипт' : 'Новый скрипт'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => { setModalOpen(false); setEditingScript(null); setEditMode('visual'); form.resetFields() }}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        width={700}
      >
        <Segmented
          value={editMode}
          onChange={(v) => {
            if (v === 'json') {
              // visual -> json: collect stages from form, convert follow_ups from string to array
              const stages = (form.getFieldValue('stages') || []) as Record<string, unknown>[]
              const converted = stages.map((s, i) => ({
                ...s,
                follow_ups: typeof s.follow_ups === 'string' && s.follow_ups
                  ? (s.follow_ups as string).split(',').map((f: string) => f.trim()).filter(Boolean)
                  : [],
                order: i,
              }))
              form.setFieldValue('stages_json', JSON.stringify(converted, null, 2))
            } else {
              // json -> visual: parse JSON, convert follow_ups from array to string
              try {
                const parsed = JSON.parse(form.getFieldValue('stages_json') || '[]') as Record<string, unknown>[]
                const converted = parsed.map((s) => ({
                  ...s,
                  follow_ups: Array.isArray(s.follow_ups) ? (s.follow_ups as string[]).join(', ') : (s.follow_ups || ''),
                }))
                form.setFieldValue('stages', converted)
              } catch { /* ignore parse errors */ }
            }
            setEditMode(v as 'visual' | 'json')
          }}
          options={[
            { label: 'Визуальный', value: 'visual' },
            { label: 'JSON', value: 'json' },
          ]}
          style={{ marginBottom: 16 }}
        />
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Название" rules={[{ required: true, message: 'Введите название' }]} tooltip="Название скрипта квалификации для идентификации в списке">
            <Input />
          </Form.Item>
          <Form.Item name="description" label="Описание" tooltip="Краткое описание назначения скрипта. Для какого типа лидов или бизнес-процесса предназначен">
            <TextArea rows={2} />
          </Form.Item>
          {editMode === 'visual' ? (
            <Form.List name="stages">
              {(fields, { add, remove, move }) => (
                <>
                  {fields.map(({ key, name, ...restField }, index) => (
                    <Card key={key} size="small" style={{ marginBottom: 8 }}
                      title={`Этап ${index + 1}`}
                      extra={
                        <Space>
                          <Button size="small" icon={<ArrowUpOutlined />} disabled={index === 0} onClick={() => move(index, index - 1)} />
                          <Button size="small" icon={<ArrowDownOutlined />} disabled={index === fields.length - 1} onClick={() => move(index, index + 1)} />
                          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => remove(name)} />
                        </Space>
                      }
                    >
                      <Form.Item {...restField} name={[name, 'stage_id']} label="ID этапа"
                        rules={[{ required: true, message: 'Выберите этап' }]}
                        tooltip="Тип этапа квалификации. Определяет, какую информацию AI будет собирать на этом шаге (потребности, бюджет, сроки и т.д.)">
                        <Select placeholder="Выберите этап" options={[
                          { value: 'needs_discovery', label: 'needs_discovery — Выявление потребностей' },
                          { value: 'budget_check', label: 'budget_check — Проверка бюджета' },
                          { value: 'timeline_check', label: 'timeline_check — Проверка сроков' },
                          { value: 'decision_maker', label: 'decision_maker — Лицо, принимающее решение' },
                          { value: 'pain_points', label: 'pain_points — Болевые точки' },
                          { value: 'solution_fit', label: 'solution_fit — Соответствие решения' },
                          { value: 'closing', label: 'closing — Закрытие' },
                        ]} allowClear />
                      </Form.Item>
                      <Form.Item {...restField} name={[name, 'question_prompt']} label="Инструкция для AI"
                        rules={[{ required: true, message: 'Введите инструкцию' }]}
                        tooltip="Системная инструкция для AI на этом этапе. Описывает, какие вопросы задавать и как вести диалог для сбора нужной информации">
                        <TextArea rows={3} placeholder="Например: Выясни бюджет клиента. Спроси о планируемых инвестициях, уточни диапазон." />
                      </Form.Item>
                      <Form.Item {...restField} name={[name, 'expected_info']} label="Ожидаемая информация"
                        tooltip="Какие данные AI должен получить для перехода к следующему этапу (например: 'бюджет клиента', 'имя ЛПР')">
                        <Input placeholder="Например: бюджет, сроки принятия решения" />
                      </Form.Item>
                      <Form.Item {...restField} name={[name, 'follow_ups']} label="Уточняющие вопросы (через запятую)"
                        tooltip="Дополнительные вопросы, если клиент дал неполный ответ. AI выберет подходящий из списка">
                        <Input placeholder="вопрос1, вопрос2, вопрос3" />
                      </Form.Item>
                      <Form.Item {...restField} name={[name, 'next_stage']} label="Следующий этап"
                        tooltip="Этап, на который AI перейдёт после завершения текущего. Если не указан — переход определяется автоматически по порядку">
                        <Select placeholder="Автоматически (по порядку)" allowClear options={[
                          { value: 'needs_discovery', label: 'needs_discovery — Выявление потребностей' },
                          { value: 'budget_check', label: 'budget_check — Проверка бюджета' },
                          { value: 'timeline_check', label: 'timeline_check — Проверка сроков' },
                          { value: 'decision_maker', label: 'decision_maker — Лицо, принимающее решение' },
                          { value: 'pain_points', label: 'pain_points — Болевые точки' },
                          { value: 'solution_fit', label: 'solution_fit — Соответствие решения' },
                          { value: 'closing', label: 'closing — Закрытие' },
                        ]} />
                      </Form.Item>
                    </Card>
                  ))}
                  <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                    Добавить этап
                  </Button>
                </>
              )}
            </Form.List>
          ) : (
            <Form.Item
              name="stages_json"
              label="Этапы (JSON)"
              rules={[{ required: true, message: 'Введите этапы' }]}
              tooltip='Массив объектов: [{"stage_id": "...", "question_prompt": "...", "expected_info": "...", "follow_ups": [...], "next_stage": "..."}]'
            >
              <TextArea rows={12} style={{ fontFamily: 'monospace' }} />
            </Form.Item>
          )}
          {editMode === 'visual' && (
            <Form.Item
              noStyle
              shouldUpdate={(prev, cur) => prev.stages !== cur.stages}
            >
              {() => {
                const currentStages = (form.getFieldValue('stages') || []) as Record<string, unknown>[]
                const stageIds = currentStages
                  .map((s) => s.stage_id as string)
                  .filter(Boolean)
                if (stageIds.length === 0) return null
                return (
                  <div style={{ marginBottom: 16 }}>
                    <Divider />
                    <Typography.Title level={5} style={{ marginBottom: 8 }}>Оценка интереса (веса этапов)</Typography.Title>
                    <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
                      Укажите вес каждого этапа для расчёта interest score. По умолчанию: 25%.
                    </Typography.Paragraph>
                    {stageIds.map((stageId) => {
                      const currentConfig = (form.getFieldValue('score_config') || {}) as Record<string, number>
                      return (
                        <Space key={stageId} style={{ marginBottom: 8, display: 'flex' }}>
                          <Typography.Text style={{ width: 180, display: 'inline-block' }}>{stageId}</Typography.Text>
                          <InputNumber
                            min={0}
                            max={100}
                            step={5}
                            value={currentConfig[stageId] ?? 25}
                            onChange={(val) => {
                              const updated = { ...currentConfig, [stageId]: val ?? 0 }
                              form.setFieldValue('score_config', updated)
                            }}
                          />
                          <Typography.Text>%</Typography.Text>
                        </Space>
                      )
                    })}
                  </div>
                )
              }}
            </Form.Item>
          )}
          <Form.Item name="score_config" hidden>
            <Input />
          </Form.Item>
          <Form.Item name="is_active" label="Активен" valuePropName="checked" initialValue={true} tooltip="Только один активный скрипт используется AI-ботом. Остальные можно сохранять как черновики">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

// --- FAQ Tab ---

function FAQTab() {
  const queryClient = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<FAQItem | null>(null)
  const [form] = Form.useForm()
  const [page, setPage] = useState(1)
  const [filterScriptId, setFilterScriptId] = useState<string | null>(null)

  const { data: qualScripts } = useQuery({
    queryKey: ['qualificationScripts'],
    queryFn: () => scriptsAPI.getScripts().then((r) => r.data),
  })

  const { data, isLoading } = useQuery({
    queryKey: ['faqItems', page, filterScriptId],
    queryFn: () => scriptsAPI.getFAQ({ page, page_size: 20, ...(filterScriptId ? { script_id: filterScriptId } : {}) }).then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (d: Partial<FAQItem>) => scriptsAPI.createFAQ(d),
    onSuccess: () => {
      message.success('FAQ создан')
      queryClient.invalidateQueries({ queryKey: ['faqItems'] })
      setModalOpen(false)
      form.resetFields()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data: d }: { id: string; data: Partial<FAQItem> }) => scriptsAPI.updateFAQ(id, d),
    onSuccess: () => {
      message.success('FAQ обновлен')
      queryClient.invalidateQueries({ queryKey: ['faqItems'] })
      setModalOpen(false)
      setEditingItem(null)
      form.resetFields()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => scriptsAPI.deleteFAQ(id),
    onSuccess: () => {
      message.success('FAQ удален')
      queryClient.invalidateQueries({ queryKey: ['faqItems'] })
    },
  })

  const syncMutation = useMutation({
    mutationFn: () => scriptsAPI.syncFAQ(),
    onSuccess: (res) => {
      message.success(`FAQ синхронизирован с Qdrant (${res.data.synced} записей)`)
    },
    onError: () => {
      message.error('Ошибка синхронизации')
    },
  })

  const [importModalOpen, setImportModalOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importScriptId, setImportScriptId] = useState<string | null>(null)

  const parseMutation = useMutation({
    mutationFn: ({ text, scriptId }: { text: string; scriptId: string | null }) => scriptsAPI.parseFAQ(text, scriptId),
    onSuccess: (res) => {
      if (res.data.length === 0) {
        message.warning('AI не смог извлечь FAQ из текста. Попробуйте другой формат.')
        return
      }
      message.success(`Импортировано ${res.data.length} FAQ записей`)
      queryClient.invalidateQueries({ queryKey: ['faqItems'] })
      setImportModalOpen(false)
      setImportText('')
      setImportScriptId(null)
    },
    onError: (err: unknown) => {
      const axiosErr = err as { code?: string; message?: string; response?: { status?: number; data?: { detail?: string | unknown[] } } }
      if (axiosErr.code === 'ECONNABORTED') {
        message.error('Превышено время ожидания. Попробуйте меньший объём текста.')
      } else if (axiosErr.response?.data?.detail) {
        const detail = axiosErr.response.data.detail
        message.error(typeof detail === 'string' ? detail : 'Ошибка валидации запроса.')
      } else {
        message.error(`Ошибка импорта (${axiosErr.response?.status ?? 'network'}): ${axiosErr.message || 'неизвестная ошибка'}`)
      }
    },
  })

  const openCreate = () => {
    setEditingItem(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (item: FAQItem) => {
    setEditingItem(item)
    form.setFieldsValue({
      question: item.question,
      answer: item.answer,
      category: item.category,
      keywords: item.keywords?.join(', '),
      is_active: item.is_active,
      qualification_script_id: item.qualification_script_id,
    })
    setModalOpen(true)
  }

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      const d = {
        question: values.question,
        answer: values.answer,
        category: values.category || null,
        keywords: values.keywords ? values.keywords.split(',').map((k: string) => k.trim()).filter(Boolean) : null,
        is_active: values.is_active ?? true,
        qualification_script_id: values.qualification_script_id || null,
      }

      if (editingItem) {
        updateMutation.mutate({ id: editingItem.id, data: d })
      } else {
        createMutation.mutate(d)
      }
    })
  }

  const columns: ColumnsType<FAQItem> = [
    { title: 'Вопрос', dataIndex: 'question', key: 'question', ellipsis: true, width: '30%' },
    { title: 'Ответ', dataIndex: 'answer', key: 'answer', ellipsis: true, width: '30%' },
    { title: 'Категория', dataIndex: 'category', key: 'category', render: (v: string | null) => v || '-' },
    {
      title: 'Статус',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (v: boolean) => v ? <Tag color="green">Активен</Tag> : <Tag>Неактивен</Tag>,
    },
    {
      title: 'Действия',
      key: 'actions',
      render: (_: unknown, record: FAQItem) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="Удалить?" onConfirm={() => deleteMutation.mutate(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Добавить FAQ
        </Button>
        <Button icon={<UploadOutlined />} onClick={() => setImportModalOpen(true)}>
          Импорт текстом
        </Button>
        <Button icon={<SyncOutlined />} onClick={() => syncMutation.mutate()} loading={syncMutation.isPending}>
          Синхронизировать с Qdrant
        </Button>
        <Select
          allowClear
          placeholder="Все скрипты"
          value={filterScriptId}
          onChange={(val) => { setFilterScriptId(val ?? null); setPage(1) }}
          options={(qualScripts || []).map((s) => ({ value: s.id, label: s.name }))}
          style={{ width: 300 }}
        />
      </Space>

      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize: 20,
          total: data?.total || 0,
          showTotal: (total) => `Всего: ${total}`,
        }}
        onChange={handleTableChange}
      />

      <Modal
        title={editingItem ? 'Редактировать FAQ' : 'Новый FAQ'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => { setModalOpen(false); setEditingItem(null); form.resetFields() }}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="question" label="Вопрос" rules={[{ required: true, message: 'Введите вопрос' }]} tooltip="Вопрос, который может задать клиент. AI ищет похожие вопросы через семантический поиск (Qdrant)">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="answer" label="Ответ" rules={[{ required: true, message: 'Введите ответ' }]} tooltip="Готовый ответ на вопрос. AI использует его как основу, адаптируя стиль под контекст диалога">
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item name="category" label="Категория" tooltip="Группировка FAQ по темам (например: 'Оплата', 'Доставка'). Помогает структурировать базу знаний">
            <Input />
          </Form.Item>
          <Form.Item name="keywords" label="Ключевые слова" tooltip="Через запятую">
            <Input placeholder="ключ1, ключ2, ключ3" />
          </Form.Item>
          <Form.Item name="qualification_script_id" label="Скрипт квалификации" tooltip="Привязка FAQ к конкретному скрипту квалификации. Если не выбран — FAQ будет глобальным">
            <Select
              allowClear
              placeholder="Глобальный (без привязки)"
              options={(qualScripts || []).map((s) => ({ value: s.id, label: s.name }))}
            />
          </Form.Item>
          <Form.Item name="is_active" label="Активен" valuePropName="checked" initialValue={true} tooltip="Неактивные FAQ не участвуют в поиске ответов. Для временного скрытия устаревших записей">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Импорт FAQ из текста"
        open={importModalOpen}
        onOk={() => parseMutation.mutate({ text: importText, scriptId: importScriptId })}
        onCancel={() => { setImportModalOpen(false); setImportText(''); setImportScriptId(null) }}
        confirmLoading={parseMutation.isPending}
        okText="Импортировать"
      >
        <Typography.Paragraph type="secondary">
          Вставьте текст с вопросами и ответами. AI разберёт его на отдельные FAQ-записи.
        </Typography.Paragraph>
        <div style={{ marginBottom: 12 }}>
          <Typography.Text>Скрипт квалификации:</Typography.Text>
          <Select
            allowClear
            placeholder="Глобальный (без привязки)"
            value={importScriptId}
            onChange={(val) => setImportScriptId(val ?? null)}
            options={(qualScripts || []).map((s) => ({ value: s.id, label: s.name }))}
            style={{ width: '100%', marginTop: 4 }}
          />
        </div>
        <TextArea
          rows={10}
          value={importText}
          onChange={(e) => setImportText(e.target.value)}
          placeholder="Вставьте текст с FAQ..."
        />
      </Modal>
    </div>
  )
}

// --- Objections Tab ---

function ObjectionsTab() {
  const queryClient = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<ObjectionScript | null>(null)
  const [form] = Form.useForm()
  const [page, setPage] = useState(1)
  const [filterScriptId, setFilterScriptId] = useState<string | null>(null)

  const { data: qualScripts } = useQuery({
    queryKey: ['qualificationScripts'],
    queryFn: () => scriptsAPI.getScripts().then((r) => r.data),
  })

  const { data, isLoading } = useQuery({
    queryKey: ['objectionScripts', page, filterScriptId],
    queryFn: () => scriptsAPI.getObjections({ page, page_size: 20, ...(filterScriptId ? { script_id: filterScriptId } : {}) }).then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (d: Partial<ObjectionScript>) => scriptsAPI.createObjection(d),
    onSuccess: () => {
      message.success('Возражение создано')
      queryClient.invalidateQueries({ queryKey: ['objectionScripts'] })
      setModalOpen(false)
      form.resetFields()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data: d }: { id: string; data: Partial<ObjectionScript> }) =>
      scriptsAPI.updateObjection(id, d),
    onSuccess: () => {
      message.success('Возражение обновлено')
      queryClient.invalidateQueries({ queryKey: ['objectionScripts'] })
      setModalOpen(false)
      setEditingItem(null)
      form.resetFields()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => scriptsAPI.deleteObjection(id),
    onSuccess: () => {
      message.success('Возражение удалено')
      queryClient.invalidateQueries({ queryKey: ['objectionScripts'] })
    },
  })

  const syncMutation = useMutation({
    mutationFn: () => scriptsAPI.syncObjections(),
    onSuccess: (res) => {
      message.success(`Возражения синхронизированы с Qdrant (${res.data.synced} записей)`)
    },
    onError: () => {
      message.error('Ошибка синхронизации')
    },
  })

  const [importModalOpen, setImportModalOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importScriptId, setImportScriptId] = useState<string | null>(null)

  const parseMutation = useMutation({
    mutationFn: ({ text, scriptId }: { text: string; scriptId: string | null }) => scriptsAPI.parseObjections(text, scriptId),
    onSuccess: (res) => {
      if (res.data.length === 0) {
        message.warning('AI не смог извлечь возражения из текста. Попробуйте другой формат.')
        return
      }
      message.success(`Импортировано ${res.data.length} возражений`)
      queryClient.invalidateQueries({ queryKey: ['objectionScripts'] })
      setImportModalOpen(false)
      setImportText('')
      setImportScriptId(null)
    },
    onError: (err: unknown) => {
      const axiosErr = err as { code?: string; message?: string; response?: { status?: number; data?: { detail?: string | unknown[] } } }
      if (axiosErr.code === 'ECONNABORTED') {
        message.error('Превышено время ожидания. Попробуйте меньший объём текста.')
      } else if (axiosErr.response?.data?.detail) {
        const detail = axiosErr.response.data.detail
        message.error(typeof detail === 'string' ? detail : 'Ошибка валидации запроса.')
      } else {
        message.error(`Ошибка импорта (${axiosErr.response?.status ?? 'network'}): ${axiosErr.message || 'неизвестная ошибка'}`)
      }
    },
  })

  const openCreate = () => {
    setEditingItem(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (item: ObjectionScript) => {
    setEditingItem(item)
    form.setFieldsValue({
      objection_pattern: item.objection_pattern,
      response_template: item.response_template,
      category: item.category,
      priority: item.priority,
      is_active: item.is_active,
      qualification_script_id: item.qualification_script_id,
    })
    setModalOpen(true)
  }

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      const d = {
        objection_pattern: values.objection_pattern,
        response_template: values.response_template,
        category: values.category || null,
        priority: values.priority ?? 0,
        is_active: values.is_active ?? true,
        qualification_script_id: values.qualification_script_id || null,
      }

      if (editingItem) {
        updateMutation.mutate({ id: editingItem.id, data: d })
      } else {
        createMutation.mutate(d)
      }
    })
  }

  const columns: ColumnsType<ObjectionScript> = [
    { title: 'Паттерн', dataIndex: 'objection_pattern', key: 'objection_pattern', ellipsis: true, width: '30%' },
    { title: 'Ответ', dataIndex: 'response_template', key: 'response_template', ellipsis: true, width: '30%' },
    { title: 'Категория', dataIndex: 'category', key: 'category', render: (v: string | null) => v || '-' },
    { title: 'Приоритет', dataIndex: 'priority', key: 'priority' },
    {
      title: 'Статус',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (v: boolean) => v ? <Tag color="green">Активен</Tag> : <Tag>Неактивен</Tag>,
    },
    {
      title: 'Действия',
      key: 'actions',
      render: (_: unknown, record: ObjectionScript) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="Удалить?" onConfirm={() => deleteMutation.mutate(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Добавить возражение
        </Button>
        <Button icon={<UploadOutlined />} onClick={() => setImportModalOpen(true)}>
          Импорт текстом
        </Button>
        <Button icon={<SyncOutlined />} onClick={() => syncMutation.mutate()} loading={syncMutation.isPending}>
          Синхронизировать с Qdrant
        </Button>
        <Select
          allowClear
          placeholder="Все скрипты"
          value={filterScriptId}
          onChange={(val) => { setFilterScriptId(val ?? null); setPage(1) }}
          options={(qualScripts || []).map((s) => ({ value: s.id, label: s.name }))}
          style={{ width: 300 }}
        />
      </Space>

      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize: 20,
          total: data?.total || 0,
          showTotal: (total) => `Всего: ${total}`,
        }}
        onChange={handleTableChange}
      />

      <Modal
        title={editingItem ? 'Редактировать возражение' : 'Новое возражение'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => { setModalOpen(false); setEditingItem(null); form.resetFields() }}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="objection_pattern"
            label="Паттерн возражения"
            rules={[{ required: true, message: 'Введите паттерн' }]}
            tooltip="Типичное возражение клиента. AI находит похожие через семантический поиск в Qdrant"
          >
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="response_template"
            label="Шаблон ответа"
            rules={[{ required: true, message: 'Введите шаблон ответа' }]}
            tooltip="Рекомендуемый ответ на возражение. AI адаптирует под контекст диалога, сохраняя ключевые аргументы"
          >
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item name="category" label="Категория" tooltip="Группировка по темам ('Цена', 'Сроки', 'Конкуренты'). Помогает анализировать частые возражения">
            <Input />
          </Form.Item>
          <Form.Item name="priority" label="Приоритет" initialValue={0} tooltip="Числовой приоритет (0 = минимальный). При нескольких совпадениях AI выбирает ответ с наивысшим приоритетом">
            <InputNumber min={0} />
          </Form.Item>
          <Form.Item name="qualification_script_id" label="Скрипт квалификации" tooltip="Привязка возражения к конкретному скрипту квалификации. Если не выбран — возражение будет глобальным">
            <Select
              allowClear
              placeholder="Глобальный (без привязки)"
              options={(qualScripts || []).map((s) => ({ value: s.id, label: s.name }))}
            />
          </Form.Item>
          <Form.Item name="is_active" label="Активен" valuePropName="checked" initialValue={true} tooltip="Неактивные возражения не участвуют в поиске. Для временного отключения устаревших шаблонов">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Импорт возражений из текста"
        open={importModalOpen}
        onOk={() => parseMutation.mutate({ text: importText, scriptId: importScriptId })}
        onCancel={() => { setImportModalOpen(false); setImportText(''); setImportScriptId(null) }}
        confirmLoading={parseMutation.isPending}
        okText="Импортировать"
      >
        <Typography.Paragraph type="secondary">
          Вставьте текст с возражениями и ответами. AI разберёт его на отдельные записи.
        </Typography.Paragraph>
        <div style={{ marginBottom: 12 }}>
          <Typography.Text>Скрипт квалификации:</Typography.Text>
          <Select
            allowClear
            placeholder="Глобальный (без привязки)"
            value={importScriptId}
            onChange={(val) => setImportScriptId(val ?? null)}
            options={(qualScripts || []).map((s) => ({ value: s.id, label: s.name }))}
            style={{ width: '100%', marginTop: 4 }}
          />
        </div>
        <TextArea
          rows={10}
          value={importText}
          onChange={(e) => setImportText(e.target.value)}
          placeholder="Вставьте текст с возражениями..."
        />
      </Modal>
    </div>
  )
}

// --- Main ScriptsPage ---

export default function ScriptsPage() {
  return (
    <div>
      <Typography.Title level={4}>Скрипты</Typography.Title>
      <Tabs
        defaultActiveKey="qualification"
        items={[
          { key: 'qualification', label: 'Скрипт квалификации', children: <QualificationTab /> },
          { key: 'faq', label: 'FAQ', children: <FAQTab /> },
          { key: 'objections', label: 'Возражения', children: <ObjectionsTab /> },
        ]}
      />
    </div>
  )
}
