import api from './client'
import type {
  AdminUser,
  Booking,
  BookingSettings,
  Channel,
  Conversation,
  ConversationDetail,
  DashboardData,
  FAQItem,
  FunnelData,
  Lead,
  LeadStats,
  ManagerDetailStats,
  ManagerWithStats,
  ObjectionScript,
  PaginatedResponse,
  QualificationScript,
  RegisterRequest,
  SystemSetting,
  TokenResponse,
} from '@/types'

// --- Auth API ---

export const authAPI = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { email, password }),

  refresh: (refreshToken: string) =>
    api.post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken }),

  register: (data: RegisterRequest) =>
    api.post<TokenResponse>('/auth/register', data),
}

// --- Leads API ---

export const leadsAPI = {
  getLeads: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<Lead>>('/leads', { params }),

  getLead: (id: string) =>
    api.get<Lead>(`/leads/${id}`),

  updateLead: (id: string, data: Partial<Lead>) =>
    api.put<Lead>(`/leads/${id}`, data),

  deleteLead: (id: string) =>
    api.delete(`/leads/${id}`),
}

// --- Conversations API ---

export const conversationsAPI = {
  getConversations: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<Conversation>>('/conversations', { params }),

  getConversation: (id: string) =>
    api.get<ConversationDetail>(`/conversations/${id}`),

  updateStatus: (id: string, status: string) =>
    api.put<Conversation>(`/conversations/${id}/status`, { status }),

  deleteConversation: (id: string) =>
    api.delete(`/conversations/${id}`),

  sendMessage: (id: string, text: string) =>
    api.post<{ id: string; content: string; created_at: string }>(`/conversations/${id}/messages`, { text }),
}

// --- Scripts API ---

export const scriptsAPI = {
  // Qualification scripts
  getScripts: () =>
    api.get<QualificationScript[]>('/scripts/qualification'),

  createScript: (data: Partial<QualificationScript>) =>
    api.post<QualificationScript>('/scripts/qualification', data),

  updateScript: (id: string, data: Partial<QualificationScript>) =>
    api.put<QualificationScript>(`/scripts/qualification/${id}`, data),

  deleteScript: (id: string) =>
    api.delete(`/scripts/qualification/${id}`),

  // FAQ
  getFAQ: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<FAQItem>>('/scripts/faq', { params }),

  createFAQ: (data: Partial<FAQItem>) =>
    api.post<FAQItem>('/scripts/faq', data),

  updateFAQ: (id: string, data: Partial<FAQItem>) =>
    api.put<FAQItem>(`/scripts/faq/${id}`, data),

  deleteFAQ: (id: string) =>
    api.delete(`/scripts/faq/${id}`),

  syncFAQ: () =>
    api.post<{ status: string; synced: number }>('/scripts/faq/sync'),

  // Objections
  getObjections: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<ObjectionScript>>('/scripts/objections', { params }),

  createObjection: (data: Partial<ObjectionScript>) =>
    api.post<ObjectionScript>('/scripts/objections', data),

  updateObjection: (id: string, data: Partial<ObjectionScript>) =>
    api.put<ObjectionScript>(`/scripts/objections/${id}`, data),

  deleteObjection: (id: string) =>
    api.delete(`/scripts/objections/${id}`),

  syncObjections: () =>
    api.post<{ status: string; synced: number }>('/scripts/objections/sync'),

  // Score config
  updateScoreConfig: (scriptId: string, scoreConfig: Record<string, number>) =>
    api.put<QualificationScript>(`/scripts/qualification/${scriptId}/score-config`, { score_config: scoreConfig }),

  // Bulk parse (longer timeout for LLM processing)
  parseFAQ: (text: string, qualificationScriptId?: string | null) =>
    api.post<FAQItem[]>('/scripts/faq/parse', { text, qualification_script_id: qualificationScriptId || null }, { timeout: 120000 }),

  parseObjections: (text: string, qualificationScriptId?: string | null) =>
    api.post<ObjectionScript[]>('/scripts/objections/parse', { text, qualification_script_id: qualificationScriptId || null }, { timeout: 120000 }),

  generateScript: (text: string) =>
    api.post<QualificationScript>('/scripts/qualification/generate', { text }, { timeout: 120000 }),
}

// --- Channels API ---

export const channelsAPI = {
  getChannels: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<Channel>>('/channels', { params }),

  getChannel: (id: string) =>
    api.get<Channel>(`/channels/${id}`),

  createChannel: (data: Partial<Channel>) =>
    api.post<Channel>('/channels', data),

  updateChannel: (id: string, data: Partial<Channel>) =>
    api.put<Channel>(`/channels/${id}`, data),

  deleteChannel: (id: string) =>
    api.delete(`/channels/${id}`),

  testChannel: (id: string) =>
    api.post<{ status: string; message: string }>(`/channels/${id}/test`),
}

// --- Bookings API ---

export const bookingsAPI = {
  getBookings: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<Booking>>('/bookings', { params }),

  createBooking: (data: Partial<Booking>) =>
    api.post<Booking>('/bookings', data),

  updateBooking: (id: string, data: Partial<Booking>) =>
    api.put<Booking>(`/bookings/${id}`, data),

  getSettings: () =>
    api.get<BookingSettings[]>('/bookings/settings'),

  updateSettings: (id: string, data: Partial<BookingSettings>) =>
    api.put<BookingSettings>(`/bookings/settings/${id}`, data),
}

// --- Settings API ---

export const settingsAPI = {
  getSettings: () =>
    api.get<SystemSetting[]>('/settings'),

  updateSettings: (settings: Record<string, unknown>) =>
    api.put<SystemSetting[]>('/settings', { settings }),
}

// --- Users API ---

export const usersAPI = {
  getUsers: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<AdminUser>>('/users', { params }),

  getUser: (id: string) =>
    api.get<AdminUser>(`/users/${id}`),

  createUser: (data: { email: string; password: string; full_name: string; role: string }) =>
    api.post<AdminUser>('/users', data),

  updateUser: (id: string, data: Partial<AdminUser & { password?: string }>) =>
    api.put<AdminUser>(`/users/${id}`, data),

  deleteUser: (id: string) =>
    api.delete(`/users/${id}`),
}

// --- Managers API ---

export const managersAPI = {
  getAll: () =>
    api.get<ManagerWithStats[]>('/managers'),

  getStats: (id: string) =>
    api.get<ManagerDetailStats>(`/managers/${id}/stats`),
}

// --- Analytics API ---

export const analyticsAPI = {
  getDashboard: (params?: { period?: string }) =>
    api.get<DashboardData>('/analytics/dashboard', { params }),

  getLeadStats: (params?: { days?: number }) =>
    api.get<LeadStats>('/analytics/leads', { params }),

  getConversionFunnel: () =>
    api.get<FunnelData>('/analytics/funnel'),

  exportCSV: () =>
    api.get('/analytics/export', { responseType: 'blob' }),
}
