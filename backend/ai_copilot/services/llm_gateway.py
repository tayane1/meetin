import json
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from django.conf import settings
from django.core.exceptions import ValidationError
import openai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class LLMGatewayError(Exception):
    """Base exception for LLM Gateway errors"""
    pass


class LLMTimeoutError(LLMGatewayError):
    """Timeout exception for LLM calls"""
    pass


class LLMRateLimitError(LLMGatewayError):
    """Rate limit exception for LLM calls"""
    pass


class LLMGateway:
    """
    Centralized LLM gateway with timeout, retry, and audit logging.
    Supports both OpenAI and Azure OpenAI providers.
    """
    
    def __init__(self):
        self.provider = getattr(settings, 'OPENAI_PROVIDER', 'openai')
        self.model = getattr(settings, 'COPILOT_MODEL', 'gpt-4-turbo-preview')
        self.timeout = getattr(settings, 'COPILOT_TIMEOUT', 30)  # seconds
        self.max_retries = getattr(settings, 'COPILOT_MAX_RETRIES', 2)
        self.use_azure = bool(getattr(settings, 'AZURE_OPENAI_ENDPOINT', None))
        
        # Initialize client
        if self.use_azure:
            self.client = openai.AzureOpenAI(
                api_key=getattr(settings, 'AZURE_OPENAI_API_KEY'),
                api_version=getattr(settings, 'AZURE_OPENAI_API_VERSION', '2023-12-01-preview'),
                azure_endpoint=getattr(settings, 'AZURE_OPENAI_ENDPOINT')
            )
        else:
            self.client = openai.OpenAI(
                api_key=getattr(settings, 'OPENAI_API_KEY')
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError))
    )
    def generate_copilot_output(
        self, 
        transcript_window: List[Dict[str, Any]], 
        meeting_context: Dict[str, Any],
        language: str = 'en',
        existing_items: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate Copilot output from transcript window.
        
        Args:
            transcript_window: List of transcript segments with speaker, text, timing
            meeting_context: Meeting metadata (title, participants, etc.)
            language: Output language ('en' or 'fr')
            existing_items: Previously accepted items to avoid duplicates
        
        Returns:
            Structured Copilot output with action items, decisions, risks, questions
        """
        start_time = time.time()
        
        try:
            # Build prompt
            prompt = self._build_copilot_prompt(
                transcript_window, 
                meeting_context, 
                language, 
                existing_items
            )
            
            # Log request (without sensitive content)
            logger.info(f"LLM request: model={self.model}, segments={len(transcript_window)}")
            
            # Make LLM call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(language)
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000,
                timeout=self.timeout
            )
            
            # Parse response
            raw_output = response.choices[0].message.content
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Log response metadata
            logger.info(f"LLM response: tokens={response.usage.total_tokens if response.usage else 'unknown'}, time={processing_time_ms}ms")
            
            # Validate and parse JSON
            parsed_output = self._parse_and_validate_output(raw_output)
            
            # Add metadata
            parsed_output['metadata'] = {
                'model': self.model,
                'provider': self.provider,
                'processing_time_ms': processing_time_ms,
                'input_segments': len(transcript_window),
                'language': language,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            return parsed_output
            
        except openai.RateLimitError as e:
            logger.error(f"LLM rate limit error: {str(e)}")
            raise LLMRateLimitError(f"Rate limit exceeded: {str(e)}")
            
        except openai.APITimeoutError as e:
            logger.error(f"LLM timeout error: {str(e)}")
            raise LLMTimeoutError(f"Request timeout: {str(e)}")
            
        except openai.APIError as e:
            logger.error(f"LLM API error: {str(e)}")
            raise LLMGatewayError(f"API error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Unexpected LLM error: {str(e)}")
            raise LLMGatewayError(f"Unexpected error: {str(e)}")
    
    def _build_copilot_prompt(
        self, 
        transcript_window: List[Dict[str, Any]], 
        meeting_context: Dict[str, Any],
        language: str,
        existing_items: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Build the Copilot prompt with transcript and context"""
        
        # Format transcript segments
        transcript_text = ""
        for segment in transcript_window:
            speaker_name = segment.get('speaker_display_name', segment.get('speaker_label', 'Unknown'))
            timestamp = segment.get('start_ms', 0) / 1000
            text = segment.get('text', '')
            transcript_text += f"[{timestamp:.1f}s] {speaker_name}: {text}\n"
        
        # Build base prompt
        if language == 'fr':
            prompt = f"""
ANALYSEZ LA TRANSCRIPTION SUIVANTE ET GÉNÉREZ DES ÉLÉMENTS D'ACTION STRUCTURÉS.

CONTEXTE DE LA RÉUNION:
- Titre: {meeting_context.get('title', 'Réunion')}
- Langue: Français
- Participants: {', '.join(meeting_context.get('participants', []))}

TRANSCRIPTION (Derniers segments):
{transcript_text}
"""
        else:
            prompt = f"""
ANALYZE THE FOLLOWING TRANSCRIPT AND GENERATE STRUCTURED ACTION ITEMS.

MEETING CONTEXT:
- Title: {meeting_context.get('title', 'Meeting')}
- Language: English
- Participants: {', '.join(meeting_context.get('participants', []))}

TRANSCRIPT (Recent segments):
{transcript_text}
"""
        
        # Add existing items to avoid duplicates
        if existing_items:
            if language == 'fr':
                prompt += f"\nÉLÉMENTS EXISTANTS À ÉVITER:\n"
                for item in existing_items:
                    prompt += f"- {item.get('title', '')}: {item.get('description', '')}\n"
            else:
                prompt += f"\nEXISTING ITEMS TO AVOID DUPLICATING:\n"
                for item in existing_items:
                    prompt += f"- {item.get('title', '')}: {item.get('description', '')}\n"
        
        # Add instructions
        if language == 'fr':
            prompt += """

INSTRUCTIONS:
1. Retournez UNIQUEMENT du JSON valide correspondant au schéma fourni
2. Chaque élément doit inclure des preuves (segment_ids et timestamps)
3. N'inventez pas de noms; utilisez les étiquettes des intervenants si incertain
4. Ne devinez pas les dates d'échéance; utilisez null si non spécifié
5. Soyez précis et basez-vous uniquement sur ce qui est dit dans la transcription

FORMAT JSON REQUIS:
{
    "language": "fr",
    "action_items": [
        {
            "title": "titre clair",
            "description": "description détaillée",
            "assignee": {"speaker_label": "Speaker 1", "user_id": null, "name": null},
            "due_date": null,
            "priority": "low|medium|high",
            "evidence": [
                {"segment_id": "uuid", "start_ms": 123000, "end_ms": 126000, "quote": "texte exact"}
            ]
        }
    ],
    "decisions": [
        {
            "text": "décision prise",
            "evidence": [{"segment_id": "uuid", "start_ms": 0, "end_ms": 0, "quote": "texte"}]
        }
    ],
    "risks": [
        {
            "text": "risque identifié",
            "severity": "low|medium|high",
            "evidence": [{"segment_id": "uuid", "start_ms": 0, "end_ms": 0, "quote": "texte"}]
        }
    ],
    "open_questions": [
        {
            "text": "question ouverte",
            "owner": {"speaker_label": "Speaker 2"},
            "evidence": [{"segment_id": "uuid", "start_ms": 0, "end_ms": 0, "quote": "texte"}]
        }
    ]
}
"""
        else:
            prompt += """

INSTRUCTIONS:
1. Return ONLY valid JSON matching the provided schema
2. Every item must include evidence (segment_ids and timestamps)
3. Do not invent names; use speaker labels if uncertain
4. Do not guess due dates; use null if not specified
5. Be precise and base only on what was said in the transcript

REQUIRED JSON FORMAT:
{
    "language": "en",
    "action_items": [
        {
            "title": "clear title",
            "description": "detailed description",
            "assignee": {"speaker_label": "Speaker 1", "user_id": null, "name": null},
            "due_date": null,
            "priority": "low|medium|high",
            "evidence": [
                {"segment_id": "uuid", "start_ms": 123000, "end_ms": 126000, "quote": "exact text"}
            ]
        }
    ],
    "decisions": [
        {
            "text": "decision made",
            "evidence": [{"segment_id": "uuid", "start_ms": 0, "end_ms": 0, "quote": "text"}]
        }
    ],
    "risks": [
        {
            "text": "identified risk",
            "severity": "low|medium|high",
            "evidence": [{"segment_id": "uuid", "start_ms": 0, "end_ms": 0, "quote": "text"}]
        }
    ],
    "open_questions": [
        {
            "text": "open question",
            "owner": {"speaker_label": "Speaker 2"},
            "evidence": [{"segment_id": "uuid", "start_ms": 0, "end_ms": 0, "quote": "text"}]
        }
    ]
}
"""
        
        return prompt
    
    def _get_system_prompt(self, language: str) -> str:
        """Get system prompt based on language"""
        if language == 'fr':
            return """Vous êtes un assistant expert spécialisé dans l'analyse des réunions. Votre tâche est d'extraire des éléments d'action, des décisions, des risques et des questions ouvertes à partir des transcriptions.

RÈGLES IMPORTANTES:
- Retournez UNIQUEMENT du JSON valide, pas de prose
- Chaque élément doit avoir des preuves avec des timestamps
- Soyez précis et basez-vous uniquement sur ce qui est dit
- N'inventez pas d'informations
- Utilisez la langue demandée pour la sortie"""
        else:
            return """You are an expert assistant specializing in meeting analysis. Your task is to extract action items, decisions, risks, and open questions from transcripts.

IMPORTANT RULES:
- Return ONLY valid JSON, no prose
- Every item must have evidence with timestamps
- Be precise and base only on what was said
- Do not invent information
- Use the requested language for output"""
    
    def _parse_and_validate_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse and validate LLM output"""
        try:
            # Try to parse JSON directly
            output = json.loads(raw_output)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            try:
                start_idx = raw_output.find('{')
                end_idx = raw_output.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = raw_output[start_idx:end_idx]
                    output = json.loads(json_str)
                else:
                    raise ValueError("No valid JSON found in response")
            except Exception:
                logger.error(f"Failed to parse JSON from LLM output: {raw_output[:200]}...")
                raise ValidationError("Invalid JSON format in LLM output")
        
        # Validate schema
        self._validate_output_schema(output)
        
        return output
    
    def _validate_output_schema(self, output: Dict[str, Any]) -> None:
        """Validate the output schema"""
        required_fields = ['language', 'action_items', 'decisions', 'risks', 'open_questions']
        
        for field in required_fields:
            if field not in output:
                raise ValidationError(f"Missing required field: {field}")
            if not isinstance(output[field], list):
                raise ValidationError(f"Field {field} must be a list")
        
        # Validate each item type has evidence
        for item_type in ['action_items', 'decisions', 'risks', 'open_questions']:
            for item in output[item_type]:
                if 'evidence' not in item or not item['evidence']:
                    raise ValidationError(f"Item in {item_type} missing required evidence")
                for evidence in item['evidence']:
                    if 'segment_id' not in evidence or 'quote' not in evidence:
                        raise ValidationError(f"Evidence missing required fields")
    
    def get_usage_stats(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get usage statistics for a time period"""
        # This would typically query a database of LLM runs
        # For now, return placeholder
        return {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'average_response_time_ms': 0,
            'total_tokens_used': 0
        }


# Global instance
llm_gateway = LLMGateway()