/** Admin user */
export interface AdminUser {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'manager'
  is_active: boolean
  created_at: string
  updated_at: string | null
}

/** Lead status enum */
export type LeadStatus = 'new' | 'qualifying' | 'qualified' | 'booked' | 'handed_off' | 'lost'

/** Score breakdown item for qualification stages */
export interface ScoreBreakdownItem {
  stage_id: string
  stage_label: string
  weight: number
  completed: boolean
  collected_info: string | null
}

/** Lead */
export interface Lead {
  id: string
  channel_id: string | null
  external_id: string | null
  name: string | null
  phone: string | null
  email: string | null
  company: string | null
  status: LeadStatus
  qualification_stage: string | null
  qualification_data: Record<string, unknown> | null
  interest_score: number
  score_breakdown?: ScoreBreakdownItem[] | null
  qualification_script_name?: string | null
  qualification_stage_label?: string | null
  source: string | null
  channel_name?: string
  channel_type?: string
  created_at: string
  updated_at: string | null
}

/** Conversation status enum */
export type ConversationStatus = 'active' | 'paused' | 'completed' | 'handed_off'

/** Message role enum */
export type MessageRole = 'user' | 'assistant' | 'system'

/** Message */
export interface Message {
  id: string
  conversation_id: string
  role: MessageRole
  content: string
  message_type: string
  metadata_: Record<string, unknown> | null
  created_at: string
}

/** Conversation */
export interface Conversation {
  id: string
  lead_id: string
  channel_id: string
  status: ConversationStatus
  started_at: string | null
  ended_at: string | null
  created_at: string
  updated_at: string | null
  manager_id: string | null
  manager_name: string | null
}

/** Conversation detail with messages */
export interface ConversationDetail extends Conversation {
  lead_name: string | null
  channel_name: string | null
  message_count: number
  messages: Message[]
}

/** Channel type enum */
export type ChannelType = 'telegram' | 'web_widget'

/** Channel */
export interface Channel {
  id: string
  type: ChannelType
  name: string
  config: Record<string, unknown> | null
  is_active: boolean
  qualification_script_id: string | null
  qualification_script_name: string | null
  created_at: string
  updated_at: string | null
}

/** Qualification script */
export interface QualificationScript {
  id: string
  name: string
  description: string | null
  stages: Record<string, unknown>[] | null
  is_active: boolean
  score_config: Record<string, number> | null
  created_at: string
  updated_at: string | null
}

/** FAQ item */
export interface FAQItem {
  id: string
  question: string
  answer: string
  category: string | null
  keywords: string[] | null
  is_active: boolean
  qualification_script_id: string | null
  created_at: string
  updated_at: string | null
}

/** Objection script */
export interface ObjectionScript {
  id: string
  objection_pattern: string
  response_template: string
  category: string | null
  priority: number
  is_active: boolean
  qualification_script_id: string | null
  created_at: string
  updated_at: string | null
}

/** Booking status enum */
export type BookingStatus = 'pending' | 'confirmed' | 'completed' | 'cancelled' | 'no_show'

/** Booking mode enum */
export type BookingMode = 'internal' | 'external_link' | 'handoff'

/** Booking */
export interface Booking {
  id: string
  lead_id: string
  manager_id: string | null
  scheduled_at: string
  duration_minutes: number
  status: BookingStatus
  meeting_link: string | null
  notes: string | null
  created_at: string
  updated_at: string | null
}

/** Booking settings */
export interface BookingSettings {
  id: string
  manager_id: string
  available_days: number[] | null
  available_hours: { start: string; end: string } | null
  slot_duration: number
  timezone: string
  booking_link: string | null
  booking_mode: BookingMode
  manager_name: string | null
}

/** System setting */
export interface SystemSetting {
  id: string
  key: string
  value: unknown
  description: string | null
}

/** Paginated response */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pages: number
}

/** Token response */
export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: AdminUser
}

/** Dashboard response */
export interface DashboardData {
  total_leads: number
  leads_today: number
  leads_week: number
  leads_month: number
  active_conversations: number
  qualification_rate: number
  bookings_count: number
  avg_interest_score: number
}

/** Lead stats */
export interface LeadsByDay {
  date: string
  count: number
}

export interface LeadStats {
  leads_by_day: LeadsByDay[]
  leads_by_status: Record<string, number>
  leads_by_channel: Record<string, number>
}

/** Funnel stage */
export interface FunnelStage {
  stage: string
  count: number
}

export interface FunnelData {
  stages: FunnelStage[]
}

/** Manager with aggregate stats */
export interface ManagerWithStats {
  id: string
  email: string
  full_name: string
  is_active: boolean
  created_at: string
  channels_count: number
  leads_count: number
  conversations_count: number
}

/** Detailed manager statistics */
export interface ManagerDetailStats {
  manager: ManagerWithStats
  leads_by_status: Record<string, number>
  conversations_by_status: Record<string, number>
  recent_activity: Array<{
    type: string
    id: string
    name: string
    status: string
    created_at: string | null
  }>
}

/** Register request */
export interface RegisterRequest {
  email: string
  password: string
  full_name: string
}
