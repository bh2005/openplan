export type DepType = 'FS' | 'SS' | 'FF' | 'SF'
export type Constraint = 'ASAP' | 'SNET' | 'MSO' | 'FNLT'
export type Status = 'open' | 'in_progress' | 'blocked' | 'done'

export interface Task {
  id: number
  parent_id: number | null
  position: number
  wbs: string
  level: number
  name: string
  duration: number
  percent: number
  constraint_type: Constraint
  constraint_date: string | null
  notes: string
  status: Status
  status_note: string
  file_count: number
  summary: boolean
  milestone: boolean
  start: string
  finish: string
  total_float: number | null
  free_float: number | null
  critical: boolean
  baseline_start: string | null
  baseline_finish: string | null
  resource_ids: number[]
  comment_count?: number
  refs?: Record<string, { ref: string; url: string }>   // externe Referenzen je System
  ext_key: string | null            // Hostname (Geräteliste-Import) – kennzeichnet ein Gerät
  attrs: Record<string, string> | null
  tpl_step: number | null           // Position des Vorlagenschritts
  tpl_id: number | null
  deadline: string | null          // Frist = „bis“ des Erledigungszeitraums (das „von“ ist constraint_type SNET + constraint_date)
  deadline_missed: boolean
  pool: boolean          // Arbeitspaket zur Selbstübernahme
}
export interface Dep { id: number; pred_id: number; succ_id: number; type: DepType; lag: number }
export interface Resource {
  id: number; name: string; max_units: number; user_id?: number | null; user_label?: string; funktion?: string; reports_to?: number | null
  cost_rate?: number; cost_center_id?: number | null; cost_type_id?: number | null   // nur mit Kostenrecht
}
export interface Absence { id: number; resource_id: number; start_date: string; end_date: string; kind: 'vacation' | 'training' | 'sick' | 'other'; note: string; source?: 'project' | 'user' }
export interface Assignment { task_id: number; resource_id: number; units: number }
export interface Project {
  id: number
  name: string
  description: string
  start_date: string
  work_days: number[]
  holidays: string[]
  holiday_state?: string
  revision: number
  finish: string | null
  task_count?: number
  updated_at: string
  owner_id: number | null
  report_enabled?: number; report_weekday?: number; report_hour?: number; report_to?: 'owner' | 'members'
  owner?: { id: number; username: string; display_name?: string } | null
  owner_name?: string | null
  access?: Access
}
export type Access = 'owner' | 'edit' | 'work' | 'view'
export interface Member { user_id: number; username: string; display_name?: string; role: 'editor' | 'viewer' }
export interface DirUser { id: number; username: string; display_name?: string; role: 'admin' | 'editor' | 'viewer' }
export interface ProjectData {
  project: Project
  tasks: Task[]
  deps: Dep[]
  resources: Resource[]
  assignments: Assignment[]
  absences: Absence[]
  critical_path: number[]
  history?: { undo: { label: string; username: string } | null; redo: { label: string; username: string } | null }
  members: Member[]
  access: Access
  cost_access: 'edit' | 'view' | 'none'
}
export interface Master { id: number; code: string; name: string }
export interface CostItem { id: number; task_id: number; cost_type_id: number | null; cost_center_id: number | null; amount: number; description: string }
export interface BudgetLine { id?: number; cost_center_id: number | null; cost_type_id: number | null; amount: number }
export interface Finance {
  currency: string; access: 'edit' | 'view'; members_see_costs: boolean
  cost_centers: Master[]; cost_types: Master[]; budget_lines: BudgetLine[]; cost_items: CostItem[]
}
export interface Actual {
  id: number; task_id: number | null; booking_date: string; cost_type_id: number | null; cost_center_id: number | null
  amount: number; reference: string; description: string; source: string
}
export interface BreakRow { id: number | null; code: string; name: string; budget: number | null; plan: number; actual: number }
export interface Budget {
  status_date: string; currency: string; has_baseline: boolean
  summary: {
    budget: number | null; bac: number; plan: number; pv: number; ev: number; ac: number
    cpi: number | null; spi: number | null; cv: number; sv: number; eac: number; etc: number; vac: number
    remaining_budget: number | null; plan_over_budget: boolean; actual_over_budget: boolean
  }
  by_cost_center: BreakRow[]; by_cost_type: BreakRow[]
  matrix: { cost_center_id: number | null; cost_type_id: number | null; plan: number; actual: number; budget: number | null }[]
  per_task: Record<string, { plan: number; bac: number; actual: number; ev: number }>
  series: { month: string; pv: number; ac: number | null }[]
}
export interface ImportReport {
  dry_run: boolean; rows: number; valid: number; duplicates: number; error_count: number; imported: number; sum: number
  errors: { row: number; message: string }[]; new_cost_centers: string[]; new_cost_types: string[]
  preview: { row: number; booking_date: string; amount: number; cc_code: string; ct_code: string; reference: string; description: string }[]
  columns: string[]
}
export interface User { id: number; username: string; display_name?: string; role: 'admin' | 'editor' | 'viewer'; email?: string; notify_email?: number | boolean; see_all?: number | boolean; lang?: 'de' | 'en' | null; theme?: 'auto' | 'light' | 'dark' | null }
export interface JournalEntry { id: number; task_id: number | null; username: string; action: string; detail: string; ts: string }
export interface TaskFile {
  id: number; task_id: number; filename: string; size: number; mime: string; comment: string
  uploaded_by: string; uploaded_at: string; kind: 'file' | 'link'; url: string
}

export interface LdapSettings {
  enabled: boolean; url: string; base_dn: string; domain: string; bind_dn: string; bind_password_set: boolean
  user_filter: string; ca_pem: string; required_group: string; admin_group: string; auditor_group: string
  default_role: 'editor' | 'viewer'; auto_create: boolean; nested_groups: boolean; from_db: boolean
}
export interface TlsStatus {
  settings: { directory_url: string; domains: string[]; email: string; ca_pem: string; auto_renew: boolean; renew_days: number; registered: boolean }
  cert: { subject: string; issuer: string; san: string[]; not_before: string; not_after: string; days_left: number; fingerprint: string } | null
  state: { ts?: string; ok?: boolean; message?: string; trigger?: string }
  running: boolean; message: string; serving: boolean
}

export interface AppNotification {
  id: number; kind: string; title: string; body: string; link: string; created_at: string; read_at: string | null
  project_name?: string | null; project_id?: number | null; task_id?: number | null
}
export interface MailSettings {
  enabled: boolean; host: string; port: number; security: 'none' | 'starttls' | 'ssl'; username: string; password_set: boolean
  from_addr: string; from_name: string; public_url: string; state: { ts?: string; ok?: boolean; message?: string; sent?: number; failed?: number }
}
export interface ReportSub {
  id: number; user_id: number; username: string; display_name?: string; email: string; kind: 'portfolio' | 'costcenter'; name: string; project_ids: number[]
  include_costs: number; weekday: number; hour: number; enabled: number; last_sent: string | null
}
export interface ReportAdmin {
  subscriptions: ReportSub[]; owners: { code: string; name: string; user_id: number; username: string; display_name?: string }[]
  projects: { id: number; name: string }[]; known_codes: string[]
}

export interface TaskComment { id: number; user_id: number | null; username: string; display_name?: string; body: string; created_at: string; can_delete: boolean }
export interface BackupState {
  settings: { enabled: boolean; hour: number; keep: number }; dir: string
  backups: { name: string; size: number; created: string }[]
  created?: { name: string; size: number }
}

export interface TemplateStep {
  position: number; name: string; role: string; duration: number; wait_days: number; pred_pos: number | null
  books_price: boolean; uses_window: boolean; takes_lead: boolean
}
export interface Template { id: number; name: string; category: string; description: string; steps: TemplateStep[] }
export interface DeviceParse {
  sheet: string; rows_total: number; columns: { index: number; name: string }[]; sample: string[][]
  mapping: Record<string, number>; fields: { key: string; label: string; required: boolean }[]; templates: string[]
}
export interface DeviceReport {
  dry_run: boolean; rows: number; new: number; updated: number; steps: number; sites_new: number; imported: number
  errors: { row: number; hostname: string; message: string }[]; error_count: number; warnings: string[]
  items: { row: number; hostname: string; standort: string; loc?: string; typ: string; action: string; steps: number }[]
  new_cost_centers: string[]; new_cost_types: string[]
}
