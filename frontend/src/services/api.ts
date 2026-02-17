import axios, { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { User, LoginResponse } from '../types';

// Étendre l'interface AxiosRequestConfig pour inclure _retry
declare module 'axios' {
  export interface InternalAxiosRequestConfig {
    _retry?: boolean;
  }
}

class ApiService {
  private api: AxiosInstance;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    this.api = axios.create({
      baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Load tokens from localStorage
    this.loadTokensFromStorage();

    // Request interceptor to add auth token
    this.api.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        if (this.accessToken) {
          config.headers.Authorization = `Bearer ${this.accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor to handle token refresh
    this.api.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;
        
        if (error.response?.status === 401 && !originalRequest._retry && this.refreshToken) {
          originalRequest._retry = true;
          
          try {
            const response = await this.refreshAccessToken();
            this.setTokens(response.data.access, this.refreshToken!);
            
            // Mettre à jour le header Authorization
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${response.data.access}`;
            }
            
            return this.api(originalRequest);
          } catch (refreshError) {
            this.clearTokens();
            // Rediriger vers login seulement si on n'est pas déjà sur la page de login
            if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
              window.location.href = '/login';
            }
            return Promise.reject(refreshError);
          }
        }
        
        return Promise.reject(error);
      }
    );
  }

  // NOUVELLE MÉTHODE : Charger les tokens depuis localStorage
  public loadTokensFromStorage(): void {
    this.accessToken = localStorage.getItem('accessToken');
    this.refreshToken = localStorage.getItem('refreshToken');
    console.log('Tokens loaded from storage:', { 
      accessToken: !!this.accessToken, 
      refreshToken: !!this.refreshToken 
    });
  }

  // MODIFIÉE : setTokens avec localStorage
  private setTokens(access: string, refresh: string): void {
    this.accessToken = access;
    this.refreshToken = refresh;
    localStorage.setItem('accessToken', access);
    localStorage.setItem('refreshToken', refresh);
    console.log('Tokens saved to storage');
  }

  // MODIFIÉE : clearTokens avec localStorage
  private clearTokens(): void {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    console.log('Tokens cleared from storage');
  }

  // Authentication methods
  async login(email: string, password: string): Promise<LoginResponse> {
    const response: AxiosResponse<LoginResponse> = await this.api.post('/auth/login/', {
      email,
      password,
    });
    
    this.setTokens(response.data.tokens.access, response.data.tokens.refresh);
    return response.data;
  }

  async register(userData: {
    email: string;
    username: string;
    password: string;
    first_name?: string;
    last_name?: string;
  }): Promise<LoginResponse> {
    const response: AxiosResponse<LoginResponse> = await this.api.post('/auth/register/', userData);
    
    this.setTokens(response.data.tokens.access, response.data.tokens.refresh);
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      if (this.refreshToken) {
        await this.api.post('/auth/logout/', {
          refresh: this.refreshToken,
        });
      }
    } catch (error) {
      console.error('Logout API error:', error);
    } finally {
      this.clearTokens();
    }
  }

  private async refreshAccessToken(): Promise<AxiosResponse<{ access: string }>> {
    return this.api.post('/auth/refresh/', {
      refresh: this.refreshToken,
    });
  }

  async getCurrentUser(): Promise<User> {
    const response: AxiosResponse<User> = await this.api.get('/auth/profile/');
    return response.data;
  }

  // Utility methods
  isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  getAuthHeaders(): Record<string, string> {
    const headers: Record<string, string> = {};
    if (this.accessToken) {
      headers.Authorization = `Bearer ${this.accessToken}`;
    }
    return headers;
  }


  // Organization methods
  async getOrganizations(): Promise<any[]> {
    const response = await this.api.get('/auth/organizations/');
    return response.data.results || response.data;
  }

  async createOrganization(name: string): Promise<any> {
    const response = await this.api.post('/auth/organizations/', { name });
    return response.data;
  }

  // Meeting methods
  async getMeetings(): Promise<any[]> {
    const response = await this.api.get('/meetings/');
    return response.data.results || response.data;
  }

  async createMeeting(meetingData: {
    organization: string;
    title: string;
    description?: string;
    language_preference?: string;
    scheduled_at?: string;
  }): Promise<any> {
    const response = await this.api.post('/meetings/', meetingData);
    return response.data;
  }

  async getMeeting(meetingId: string): Promise<any> {
    const response = await this.api.get(`/meetings/${meetingId}/`);
    return response.data;
  }

  async updateMeeting(meetingId: string, meetingData: any): Promise<any> {
    const response = await this.api.patch(`/meetings/${meetingId}/`, meetingData);
    return response.data;
  }

  async deleteMeeting(meetingId: string): Promise<void> {
    await this.api.delete(`/meetings/${meetingId}/`);
  }

  // Live session methods
  async startLiveSession(meetingId: string, config?: any): Promise<any> {
    const response = await this.api.post(`/meetings/${meetingId}/live/start/`, config || {});
    return response.data;
  }

  async stopLiveSession(meetingId: string): Promise<any> {
    const response = await this.api.post(`/meetings/${meetingId}/live/stop/`);
    return response.data;
  }

  async getLiveSessionStatus(meetingId: string): Promise<any> {
    const response = await this.api.get(`/meetings/${meetingId}/live/status/`);
    return response.data;
  }

  // Recording methods
  async initiateRecording(meetingId: string): Promise<any> {
    const response = await this.api.post(`/meetings/${meetingId}/recordings/initiate/`);
    return response.data;
  }

  async uploadRecording(meetingId: string, audioFile: Blob | File): Promise<any> {
    const formData = new FormData();
    // Ensure the file has a proper filename for backend validation
    if (audioFile instanceof File) {
      formData.append('audio', audioFile, audioFile.name);
    } else {
      // For Blob (e.g. live recording), derive extension from MIME type
      const ext = audioFile.type === 'audio/webm' ? '.webm'
        : audioFile.type === 'audio/wav' ? '.wav'
        : audioFile.type === 'audio/mpeg' ? '.mp3'
        : audioFile.type === 'audio/mp4' ? '.m4a'
        : '.webm';
      formData.append('audio', audioFile, `recording${ext}`);
    }
    const response = await this.api.post(`/meetings/${meetingId}/recordings/upload/`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async transcribeRecording(meetingId: string, recordingId: string): Promise<any> {
    const response = await this.api.post(`/meetings/${meetingId}/recordings/${recordingId}/transcribe/`);
    return response.data;
  }

  async completeRecording(recordingId: string, data: {
    size_bytes?: number;
    duration_ms?: number;
  }): Promise<any> {
    const response = await this.api.post(`/recordings/${recordingId}/complete/`, data);
    return response.data;
  }

  // Transcript methods
  async getTranscript(meetingId: string): Promise<any> {
    const response = await this.api.get(`/transcription/meetings/${meetingId}/transcript/`);
    return response.data;
  }

  // Minutes methods
  async generateMinutes(meetingId: string): Promise<any> {
    const response = await this.api.post(`/transcription/meetings/${meetingId}/minutes/generate/`);
    return response.data;
  }

  async getMinutes(meetingId: string): Promise<any> {
    const response = await this.api.get(`/transcription/meetings/${meetingId}/minutes/`);
    return response.data;
  }

  async updateMinutes(meetingId: string, minutesData: any): Promise<any> {
    const response = await this.api.patch(`/transcription/meetings/${meetingId}/minutes/`, minutesData);
    return response.data;
  }

  async getMinutesVersions(meetingId: string): Promise<any[]> {
    const response = await this.api.get(`/transcription/meetings/${meetingId}/minutes/versions/`);
    return response.data;
  }

  // Action items methods
  async getActionItems(meetingId: string): Promise<any[]> {
    const response = await this.api.get(`/transcription/meetings/${meetingId}/action-items/`);
    return response.data;
  }

  async createActionItem(meetingId: string, itemData: any): Promise<any> {
    const response = await this.api.post(`/transcription/meetings/${meetingId}/action-items/`, itemData);
    return response.data;
  }

  async updateActionItem(meetingId: string, itemId: string, itemData: any): Promise<any> {
    const response = await this.api.patch(`/transcription/meetings/${meetingId}/action-items/${itemId}/`, itemData);
    return response.data;
  }

  async deleteActionItem(meetingId: string, itemId: string): Promise<void> {
    await this.api.delete(`/transcription/meetings/${meetingId}/action-items/${itemId}/`);
  }

  // Speaker methods
  async updateSpeaker(meetingId: string, speakerId: string, displayName: string): Promise<any> {
    const response = await this.api.patch(`/meetings/${meetingId}/speakers/${speakerId}/`, {
      display_name: displayName,
    });
    return response.data;
  }
}

export const apiService = new ApiService();
export default apiService;