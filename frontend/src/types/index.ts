export interface User {
  id: string;
  email: string;
  username: string;
  first_name?: string;
  last_name?: string;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  owner: User;
  member_count: number;
  created_at: string;
}

export interface Speaker {
  id: string;
  label: string;
  display_name?: string;
  created_at: string;
}

export interface Meeting {
  id: string;
  organization: string;
  organization_name: string;
  created_by: string;
  title: string;
  description?: string;
  language_preference: 'en' | 'fr' | 'auto';
  scheduled_at?: string;
  created_at: string;
  updated_at: string;
  live_sessions: LiveSession[];
  recordings: Recording[];
  speakers: Speaker[];
}

export interface LiveSession {
  id: string;
  status: 'active' | 'ended' | 'failed';
  provider: string;
  provider_session_id?: string;
  config_json: Record<string, any>;
  error_message?: string;
  started_at: string;
  ended_at?: string;
}

export interface Recording {
  id: string;
  storage_key: string;
  mime_type: string;
  duration_ms?: number;
  size_bytes?: number;
  status: 'created' | 'uploaded' | 'processing' | 'ready' | 'failed';
  created_at: string;
  uploaded_at?: string;
}

export interface TranscriptSegment {
  id: string;
  start_ms: number;
  end_ms: number;
  speaker?: string;
  speaker_label: string;
  speaker_display_name?: string;
  speaker_label_raw: string;
  text: string;
  confidence?: number;
  is_final: boolean;
  created_at: string;
}

export interface Transcript {
  id: string;
  meeting: string;
  recording?: string;
  live_session?: string;
  provider: string;
  language_detected?: string;
  segments: TranscriptSegment[];
  created_at: string;
}

export interface ActionItem {
  id: string;
  meeting: string;
  minutes: string;
  title: string;
  description?: string;
  assignee?: string;
  assignee_email?: string;
  due_date?: string;
  priority: 'low' | 'medium' | 'high';
  status: 'open' | 'in_progress' | 'done' | 'blocked';
  source_segment_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface Minutes {
  id: string;
  meeting: string;
  transcript: string;
  content_json: Record<string, any>;
  content_md: string;
  output_language: 'en' | 'fr';
  generated_by_model?: string;
  model_version?: string;
  action_items: ActionItem[];
  created_at: string;
  updated_at: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginResponse {
  user: User;
  tokens: AuthTokens;
}

export interface WebSocketMessage {
  type: 'transcript_segment' | 'speaker_updated' | 'session_status' | 'error' | 'control_response';
  data?: any;
  speaker_label?: string;
  display_name?: string;
  status?: string;
  message?: string;
}

export interface TranscriptSegmentData {
  id: string;
  speaker_label: string;
  speaker_display_name?: string;
  text: string;
  confidence?: number;
  is_final: boolean;
  start_ms: number;
  end_ms: number;
  timestamp: string;
}