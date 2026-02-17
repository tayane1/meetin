import React, { createContext, useContext, useReducer, useEffect, ReactNode, useCallback } from 'react';
import { Meeting, LiveSession, TranscriptSegment, Speaker } from '../types';
import apiService from '../services/api';
import wsService from '../services/websocket';

interface MeetingState {
  meeting: Meeting | null;
  liveSession: LiveSession | null;
  transcriptSegments: TranscriptSegment[];
  speakers: Speaker[];
  isLive: boolean;
  isRecording: boolean;
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
  isLoading: boolean;
  error: string | null;
}

type MeetingAction =
  | { type: 'SET_MEETING'; payload: Meeting }
  | { type: 'SET_LIVE_SESSION'; payload: LiveSession | null }
  | { type: 'ADD_TRANSCRIPT_SEGMENT'; payload: TranscriptSegment }
  | { type: 'UPDATE_TRANSCRIPT_SEGMENTS'; payload: TranscriptSegment[] }
  | { type: 'SET_SPEAKERS'; payload: Speaker[] }
  | { type: 'UPDATE_SPEAKER'; payload: { speaker_label: string; display_name: string } }
  | { type: 'SET_LIVE_STATUS'; payload: boolean }
  | { type: 'SET_RECORDING_STATUS'; payload: boolean }
  | { type: 'SET_CONNECTION_STATUS'; payload: 'disconnected' | 'connecting' | 'connected' | 'error' }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'CLEAR_ERROR' };

const initialState: MeetingState = {
  meeting: null,
  liveSession: null,
  transcriptSegments: [],
  speakers: [],
  isLive: false,
  isRecording: false,
  connectionStatus: 'disconnected',
  isLoading: false,
  error: null,
};

const meetingReducer = (state: MeetingState, action: MeetingAction): MeetingState => {
  switch (action.type) {
    case 'SET_MEETING':
      return {
        ...state,
        meeting: action.payload,
        speakers: action.payload.speakers,
        transcriptSegments: [],
      };
    case 'SET_LIVE_SESSION':
      return {
        ...state,
        liveSession: action.payload,
        isLive: action.payload?.status === 'active' || false,
      };
    case 'ADD_TRANSCRIPT_SEGMENT':
      return {
        ...state,
        transcriptSegments: [...state.transcriptSegments, action.payload],
      };
    case 'UPDATE_TRANSCRIPT_SEGMENTS':
      return {
        ...state,
        transcriptSegments: action.payload,
      };
    case 'SET_SPEAKERS':
      return {
        ...state,
        speakers: action.payload,
      };
    case 'UPDATE_SPEAKER':
      return {
        ...state,
        speakers: state.speakers.map(speaker =>
          speaker.label === action.payload.speaker_label
            ? { ...speaker, display_name: action.payload.display_name }
            : speaker
        ),
      };
    case 'SET_LIVE_STATUS':
      return {
        ...state,
        isLive: action.payload,
      };
    case 'SET_RECORDING_STATUS':
      return {
        ...state,
        isRecording: action.payload,
      };
    case 'SET_CONNECTION_STATUS':
      return {
        ...state,
        connectionStatus: action.payload,
      };
    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload,
      };
    case 'SET_ERROR':
      return {
        ...state,
        error: action.payload,
      };
    case 'CLEAR_ERROR':
      return {
        ...state,
        error: null,
      };
    default:
      return state;
  }
};

interface MeetingContextType extends MeetingState {
  loadMeeting: (meetingId: string) => Promise<void>;
  startLiveSession: (config?: any) => Promise<void>;
  stopLiveSession: () => Promise<void>;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<void>;
  updateSpeaker: (speakerLabel: string, displayName: string) => Promise<void>;
  clearError: () => void;
}

const MeetingContext = createContext<MeetingContextType | undefined>(undefined);

interface MeetingProviderProps {
  children: ReactNode;
  meetingId?: string;
}

export const MeetingProvider: React.FC<MeetingProviderProps> = ({ children, meetingId }) => {
  const [state, dispatch] = useReducer(meetingReducer, initialState);


  useEffect(() => {
    // Set up WebSocket event handlers
    wsService.on('transcript_segment', handleTranscriptSegment);
    wsService.on('speaker_updated', handleSpeakerUpdated);
    wsService.on('session_status', handleSessionStatus);
    wsService.on('error', handleError);

    return () => {
      wsService.off('transcript_segment', handleTranscriptSegment);
      wsService.off('speaker_updated', handleSpeakerUpdated);
      wsService.off('session_status', handleSessionStatus);
      wsService.off('error', handleError);
    };
  }, []);

  const handleTranscriptSegment = (data: any): void => {
    dispatch({ type: 'ADD_TRANSCRIPT_SEGMENT', payload: data });
  };

  const handleSpeakerUpdated = (data: { speaker_label: string; display_name: string }): void => {
    dispatch({ type: 'UPDATE_SPEAKER', payload: data });
  };

  const handleSessionStatus = (data: { status: string; message?: string }): void => {
    if (data.status === 'disconnected') {
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'disconnected' });
      dispatch({ type: 'SET_LIVE_STATUS', payload: false });
    }
  };

  const handleError = (data: { message: string }): void => {
    dispatch({ type: 'SET_ERROR', payload: data.message });
    dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'error' });
  };
  
  const connectWebSocket = useCallback(async (id: string): Promise<void> => {
    dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'connecting' });

    try {
      // Get access token from localStorage or apiService
      const token = localStorage.getItem('accessToken');
      if (!token) {
        throw new Error('No authentication token available');
      }

      await wsService.connect(id, token);
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'connected' });
    } catch (error) {
      console.error('WebSocket connection failed:', error);
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'error' });
      dispatch({ type: 'SET_ERROR', payload: 'Failed to connect to live session' });
    }
  }, []);

  const loadMeeting = useCallback(async (id: string): Promise<void> => {
  dispatch({ type: 'SET_LOADING', payload: true });
  dispatch({ type: 'CLEAR_ERROR' });

    try {
      const meeting = await apiService.getMeeting(id);
      dispatch({ type: 'SET_MEETING', payload: meeting });

      // Check for active live session
      if (meeting.live_sessions.length > 0) {
        const activeSession = meeting.live_sessions.find(
          (session: LiveSession) => session.status === 'active'
        );
        if (activeSession) {
          dispatch({ type: 'SET_LIVE_SESSION', payload: activeSession });
          await connectWebSocket(id);
        }
      }
      
      // Load existing transcript
      try {
        const transcriptData = await apiService.getTranscript(id);
        if (transcriptData && transcriptData.segments && transcriptData.segments.length > 0) {
          transcriptData.segments.forEach((segment: any) => {
            dispatch({ type: 'ADD_TRANSCRIPT_SEGMENT', payload: segment });
          });
        }
      } catch (e) {
        // No transcript yet, that's OK
      }
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to load meeting';
      dispatch({ type: 'SET_ERROR', payload: errorMessage });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  },[connectWebSocket]);
  
  useEffect(() => {
    if (meetingId) {
      loadMeeting(meetingId);
    }

    return () => {
      wsService.disconnect();
    };
  }, [meetingId, loadMeeting]);

  

  const startLiveSession = async (config?: any): Promise<void> => {
    if (!state.meeting) return;

    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'CLEAR_ERROR' });

    try {
      const session = await apiService.startLiveSession(state.meeting.id, config);
      dispatch({ type: 'SET_LIVE_SESSION', payload: session });
      await connectWebSocket(state.meeting.id);
      
      // Start audio capture
      await wsService.startAudioCapture();
    } catch (error: any) {
      const errorMessage = error.response?.data?.error || 'Failed to start live session';
      dispatch({ type: 'SET_ERROR', payload: errorMessage });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const stopLiveSession = async (): Promise<void> => {
    if (!state.meeting) return;

    try {
      await apiService.stopLiveSession(state.meeting.id);
      wsService.stopAudioCapture();
      wsService.disconnect();
      dispatch({ type: 'SET_LIVE_SESSION', payload: null });
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'disconnected' });
    } catch (error: any) {
      const errorMessage = error.response?.data?.error || 'Failed to stop live session';
      dispatch({ type: 'SET_ERROR', payload: errorMessage });
    }
  };

  const startRecording = async (): Promise<void> => {
    if (!state.meeting) return;

    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'CLEAR_ERROR' });

    try {
      const recordingData = await apiService.initiateRecording(state.meeting.id);
      dispatch({ type: 'SET_RECORDING_STATUS', payload: true });
      
      // Here you would handle the actual recording upload
      // For now, we'll just simulate it
      console.log('Recording initiated:', recordingData);
    } catch (error: any) {
      const errorMessage = error.response?.data?.error || 'Failed to start recording';
      dispatch({ type: 'SET_ERROR', payload: errorMessage });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const stopRecording = async (): Promise<void> => {
    dispatch({ type: 'SET_RECORDING_STATUS', payload: false });
    // Handle recording completion
  };

  const updateSpeaker = async (speakerLabel: string, displayName: string): Promise<void> => {
    if (!state.meeting) return;

    try {
      await apiService.updateSpeaker(state.meeting.id, speakerLabel, displayName);
      dispatch({ type: 'UPDATE_SPEAKER', payload: { speaker_label: speakerLabel, display_name: displayName } });
      
      // Also send via WebSocket for real-time updates
      wsService.sendSpeakerMapping(speakerLabel, displayName);
    } catch (error: any) {
      const errorMessage = error.response?.data?.error || 'Failed to update speaker';
      dispatch({ type: 'SET_ERROR', payload: errorMessage });
    }
  };

  const clearError = (): void => {
    dispatch({ type: 'CLEAR_ERROR' });
  };

  const value: MeetingContextType = {
    ...state,
    loadMeeting,
    startLiveSession,
    stopLiveSession,
    startRecording,
    stopRecording,
    updateSpeaker,
    clearError,
  };

  return <MeetingContext.Provider value={value}>{children}</MeetingContext.Provider>;
};

export const useMeeting = (): MeetingContextType => {
  const context = useContext(MeetingContext);
  if (context === undefined) {
    throw new Error('useMeeting must be used within a MeetingProvider');
  }
  return context;
};