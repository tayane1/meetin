import logging
import os
import json
import uuid
import httpx
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('meetin')
from django.core.files.base import ContentFile
from meetings.models import LiveSession, Meeting, Speaker, Recording
from transcription.models import Transcript, TranscriptSegment
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class TranscriptionService:
    def __init__(self):
        self.api_key = getattr(settings, 'DEEPGRAM_API_KEY', None)
        self.active_connections = {}
    
    def start_live_session(self, live_session):
        """Start a live transcription session"""
        if not self.api_key:
            raise Exception("DEEPGRAM_API_KEY not configured")
        
        session_id = str(uuid.uuid4())
        self.active_connections[str(live_session.id)] = {
            'session_id': session_id,
            'session': live_session,
            'meeting': live_session.meeting,
            'audio_chunks': []
        }
        return session_id
    
    def stop_live_session(self, live_session):
        """Stop a live transcription session"""
        session_key = str(live_session.id)
        if session_key in self.active_connections:
            del self.active_connections[session_key]
    
    async def process_audio_chunk(self, live_session, audio_data):
        """Process audio chunk - store for batch processing"""
        session_key = str(live_session.id)
        if session_key in self.active_connections:
            self.active_connections[session_key]['audio_chunks'].append(audio_data)
    
    async def process_binary_audio(self, live_session, binary_data):
        """Process binary audio data"""
        await self.process_audio_chunk(live_session, binary_data)


class BatchTranscriptionService:
    """Service for batch transcription of uploaded audio files"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'DEEPGRAM_API_KEY', None)
    
    def transcribe_recording(self, recording):
        """Transcribe a recording using Deepgram"""
        if not self.api_key:
            raise Exception("DEEPGRAM_API_KEY not configured")
        
        meeting = recording.meeting
        file_path = os.path.join(settings.MEDIA_ROOT, recording.storage_key)

        # Path traversal protection
        resolved_path = os.path.realpath(file_path)
        media_root = os.path.realpath(settings.MEDIA_ROOT)
        if not resolved_path.startswith(media_root + os.sep):
            raise Exception("Invalid storage key")

        if not os.path.exists(file_path):
            raise Exception("Recording file not found")
        
        try:
            recording.status = Recording.Status.PROCESSING
            recording.save()
            
            with open(file_path, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            language = meeting.language_preference if meeting.language_preference != 'auto' else None
            
            headers = {
                'Authorization': f'Token {self.api_key}',
                'Content-Type': 'audio/webm',
            }
            
            params = {
                'model': 'nova-2',
                'punctuate': 'true',
                'smart_format': 'true',
                'diarize': 'true',
                'utterances': 'true',
            }
            
            if language:
                params['language'] = language
            else:
                params['detect_language'] = 'true'
            
            response = httpx.post(
                'https://api.deepgram.com/v1/listen',
                headers=headers,
                params=params,
                content=audio_data,
                timeout=300.0
            )
            
            if response.status_code != 200:
                logger.error("Deepgram API error (status %d): %s", response.status_code, response.text)
                raise Exception("Transcription service returned an error")
            
            result = response.json()
            self._process_results(recording, result)
            
            recording.status = Recording.Status.READY
            recording.save()
            
            return True
            
        except Exception as e:
            recording.status = Recording.Status.FAILED
            recording.save()
            raise Exception(f"Transcription failed: {str(e)}")
    
    def _process_results(self, recording, result):
        """Process Deepgram transcription results"""
        meeting = recording.meeting
        
        results = result.get('results', {})
        channels = results.get('channels', [])
        
        if not channels:
            return
        
        channel = channels[0]
        alternatives = channel.get('alternatives', [])
        
        if not alternatives:
            return
        
        detected_language = results.get('metadata', {}).get('detected_language', 'unknown')
        
        transcript = Transcript.objects.create(
            meeting=meeting,
            recording=recording,
            provider='deepgram',
            language_detected=detected_language
        )
        
        utterances = results.get('utterances', [])
        
        if utterances:
            for utterance in utterances:
                speaker_id = utterance.get('speaker', 0)
                speaker_label = f"Speaker {speaker_id}"
                
                speaker, _ = Speaker.objects.get_or_create(
                    meeting=meeting,
                    label=speaker_label,
                    defaults={'display_name': None}
                )
                
                TranscriptSegment.objects.create(
                    transcript=transcript,
                    start_ms=int(utterance.get('start', 0) * 1000),
                    end_ms=int(utterance.get('end', 0) * 1000),
                    speaker=speaker,
                    speaker_label_raw=speaker_label,
                    text=utterance.get('transcript', ''),
                    confidence=utterance.get('confidence', 0.0),
                    is_final=True
                )
        else:
            alternative = alternatives[0]
            words = alternative.get('words', [])
            
            if words:
                current_speaker = None
                current_text = []
                start_time = 0
                end_time = 0
                
                for word in words:
                    speaker_id = word.get('speaker', 0)
                    
                    if current_speaker is None:
                        current_speaker = speaker_id
                        start_time = word.get('start', 0)
                    
                    if speaker_id != current_speaker:
                        speaker_label = f"Speaker {current_speaker}"
                        speaker, _ = Speaker.objects.get_or_create(
                            meeting=meeting,
                            label=speaker_label,
                            defaults={'display_name': None}
                        )
                        
                        TranscriptSegment.objects.create(
                            transcript=transcript,
                            start_ms=int(start_time * 1000),
                            end_ms=int(end_time * 1000),
                            speaker=speaker,
                            speaker_label_raw=speaker_label,
                            text=' '.join(current_text),
                            confidence=alternative.get('confidence', 0.0),
                            is_final=True
                        )
                        
                        current_speaker = speaker_id
                        current_text = []
                        start_time = word.get('start', 0)
                    
                    current_text.append(word.get('word', ''))
                    end_time = word.get('end', 0)
                
                if current_text:
                    speaker_label = f"Speaker {current_speaker}"
                    speaker, _ = Speaker.objects.get_or_create(
                        meeting=meeting,
                        label=speaker_label,
                        defaults={'display_name': None}
                    )
                    
                    TranscriptSegment.objects.create(
                        transcript=transcript,
                        start_ms=int(start_time * 1000),
                        end_ms=int(end_time * 1000),
                        speaker=speaker,
                        speaker_label_raw=speaker_label,
                        text=' '.join(current_text),
                        confidence=alternative.get('confidence', 0.0),
                        is_final=True
                    )
            else:
                full_transcript = alternative.get('transcript', '')
                if full_transcript:
                    speaker_label = "Speaker 0"
                    speaker, _ = Speaker.objects.get_or_create(
                        meeting=meeting,
                        label=speaker_label,
                        defaults={'display_name': None}
                    )
                    
                    TranscriptSegment.objects.create(
                        transcript=transcript,
                        start_ms=0,
                        end_ms=0,
                        speaker=speaker,
                        speaker_label_raw=speaker_label,
                        text=full_transcript,
                        confidence=alternative.get('confidence', 0.0),
                        is_final=True
                    )
