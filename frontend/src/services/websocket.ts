import { WebSocketMessage } from '../types';

export class WebSocketService {
  private ws: WebSocket | null = null;
  private meetingId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private messageHandlers: Map<string, (data: any) => void> = new Map();
  private audioProcessor: ScriptProcessorNode | null = null;
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;

  constructor() {
    this.setupMessageHandlers();
  }

  private setupMessageHandlers(): void {
    this.messageHandlers.set('transcript_segment', this.handleTranscriptSegment.bind(this));
    this.messageHandlers.set('speaker_updated', this.handleSpeakerUpdated.bind(this));
    this.messageHandlers.set('session_status', this.handleSessionStatus.bind(this));
    this.messageHandlers.set('error', this.handleError.bind(this));
  }

  connect(meetingId: string, token: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.meetingId = meetingId;
      
      const wsUrl = `${this.getWebSocketURL()}/ws/meetings/${meetingId}/live/?token=${token}`;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      this.ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        this.handleDisconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };
    });
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    
    this.stopAudioCapture();
    this.meetingId = null;
  }

  private handleDisconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts && this.meetingId) {
      setTimeout(() => {
        this.reconnectAttempts++;
        console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        // Reconnection logic would need token - store it for reconnection
      }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts));
    }
  }

  private handleMessage(message: WebSocketMessage): void {
    const handler = this.messageHandlers.get(message.type);
    if (handler) {
      handler(message);
    } else {
      console.log('Unhandled message type:', message.type, message);
    }
  }

  private handleTranscriptSegment(message: WebSocketMessage): void {
    if (message.data) {
      this.emit('transcript_segment', message.data);
    }
  }

  private handleSpeakerUpdated(message: WebSocketMessage): void {
    if (message.speaker_label && message.display_name) {
      this.emit('speaker_updated', {
        speaker_label: message.speaker_label,
        display_name: message.display_name,
      });
    }
  }

  private handleSessionStatus(message: WebSocketMessage): void {
    this.emit('session_status', {
      status: message.status,
      message: message.message,
    });
  }

  private handleError(message: WebSocketMessage): void {
    this.emit('error', {
      message: message.message,
    });
  }

  // Audio capture methods
  async startAudioCapture(): Promise<void> {
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
          channelCount: 1,
        },
        video: false,
      });

      this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000,
      });

      const source = this.audioContext.createMediaStreamSource(this.mediaStream);
      this.audioProcessor = this.audioContext.createScriptProcessor(4096, 1, 1);

      this.audioProcessor.onaudioprocess = (event) => {
        const inputData = event.inputBuffer.getChannelData(0);
        this.sendAudioData(inputData);
      };

      source.connect(this.audioProcessor);
      this.audioProcessor.connect(this.audioContext.destination);

      console.log('Audio capture started');
    } catch (error) {
      console.error('Error starting audio capture:', error);
      throw error;
    }
  }

  stopAudioCapture(): void {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }

    if (this.audioProcessor) {
      this.audioProcessor.disconnect();
      this.audioProcessor = null;
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    console.log('Audio capture stopped');
  }

  private sendAudioData(audioData: Float32Array): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      // Convert Float32Array to Int16Array (16-bit PCM)
      const pcmData = new Int16Array(audioData.length);
      for (let i = 0; i < audioData.length; i++) {
        pcmData[i] = Math.max(-32768, Math.min(32767, audioData[i] * 32767));
      }

      // Send as binary data
      this.ws.send(pcmData.buffer);
    }
  }

  // Control messages
  sendControlMessage(control: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'control',
        control: control,
      }));
    }
  }

  sendSpeakerMapping(speakerLabel: string, displayName: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'speaker_mapping',
        speaker_label: speakerLabel,
        display_name: displayName,
      }));
    }
  }

  // Event handling
  private eventListeners: Map<string, ((data: any) => void)[]> = new Map();

  on(event: string, callback: (data: any) => void): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event)!.push(callback);
  }

  off(event: string, callback: (data: any) => void): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  private emit(event: string, data: any): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.forEach(callback => callback(data));
    }
  }

  private getWebSocketURL(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = process.env.REACT_APP_WS_HOST || 'localhost:8000';
    return `${protocol}//${host}`;
  }

  // Utility methods
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  getConnectionState(): string {
    if (!this.ws) return 'disconnected';
    
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING: return 'connecting';
      case WebSocket.OPEN: return 'connected';
      case WebSocket.CLOSING: return 'closing';
      case WebSocket.CLOSED: return 'closed';
      default: return 'unknown';
    }
  }
}

export const wsService = new WebSocketService();
export default wsService;