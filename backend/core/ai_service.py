import json
import uuid
from typing import Dict, List, Any, Optional
from django.conf import settings
from transcription.models import Transcript, TranscriptSegment, Minutes, ActionItem
from meetings.models import Meeting


class AIService:
    """Service for AI-powered minutes generation using OpenAI or Azure OpenAI"""
    
    def __init__(self):
        self.model_name = getattr(settings, 'OPENAI_MODEL', 'gpt-4-turbo-preview')
        self.model_version = '1.0'
        self.use_azure = bool(getattr(settings, 'AZURE_OPENAI_ENDPOINT', None))
        
        if self.use_azure:
            self.client = self._init_azure_client()
        else:
            self.client = self._init_openai_client()
    
    def _init_openai_client(self):
        """Initialize OpenAI client"""
        try:
            import openai
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            return client
        except ImportError:
            raise Exception("OpenAI package not installed")
    
    def _init_azure_client(self):
        """Initialize Azure OpenAI client"""
        try:
            import openai
            client = openai.AzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
            )
            return client
        except ImportError:
            raise Exception("OpenAI package not installed")
    
    def generate_minutes(self, transcript: Transcript, language: str = 'en') -> Dict[str, Any]:
        """Generate meeting minutes from transcript using AI"""
        
        # Prepare transcript text for AI
        transcript_text = self._prepare_transcript_text(transcript)
        
        # Build prompt based on language
        if language == 'fr':
            prompt = self._build_french_prompt(transcript_text)
        else:
            prompt = self._build_english_prompt(transcript_text)
        
        try:
            # Call AI API
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert assistant that generates comprehensive meeting minutes from transcripts. Always output valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse and validate response
            ai_response = response.choices[0].message.content
            
            try:
                minutes_data = json.loads(ai_response)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                minutes_data = self._extract_json_from_response(ai_response)
            
            # Validate and structure the data
            structured_minutes = self._structure_minutes_data(minutes_data, transcript, language)
            
            return structured_minutes
            
        except Exception as e:
            raise Exception(f"AI minutes generation failed: {str(e)}")
    
    def _prepare_transcript_text(self, transcript: Transcript) -> str:
        """Prepare transcript text for AI processing"""
        segments = transcript.segments.filter(is_final=True).order_by('start_ms')
        
        transcript_lines = []
        for segment in segments:
            speaker_name = segment.speaker.display_name if segment.speaker else segment.speaker_label_raw
            timestamp = segment.start_ms / 1000  # Convert to seconds
            
            line = f"[{timestamp:.1f}s] {speaker_name}: {segment.text}"
            transcript_lines.append(line)
        
        return "\n".join(transcript_lines)
    
    def _build_english_prompt(self, transcript_text: str) -> str:
        """Build prompt for English minutes generation"""
        return f"""
Analyze the following meeting transcript and generate comprehensive meeting minutes in JSON format.

TRANSCRIPT:
{transcript_text}

Please generate minutes with the following structure:
{{
    "summary": "Brief executive summary of the meeting",
    "key_points": [
        "Important discussion points and decisions made"
    ],
    "decisions": [
        {{
            "title": "Decision title",
            "description": "Detailed description of the decision",
            "made_by": "Person or group who made the decision",
            "timestamp": "Approximate time when decision was made"
        }}
    ],
    "action_items": [
        {{
            "title": "Action item title",
            "description": "What needs to be done",
            "assignee": "Person responsible (if mentioned)",
            "due_date": "Due date (if mentioned)",
            "priority": "high/medium/low",
            "timestamp": "When this was assigned"
        }}
    ],
    "next_steps": [
        "Follow-up items and next meeting suggestions"
    ],
    "attendees": [
        "List of people who participated"
    ]
}}

Important guidelines:
- Extract actual information from the transcript, don't invent details
- Include timestamps for key items (use approximate times from transcript)
- Mark assignee as null if not explicitly mentioned
- Use realistic priority levels based on context
- Ensure all JSON is properly formatted and valid
- Focus on concrete decisions and action items
"""
    
    def _build_french_prompt(self, transcript_text: str) -> str:
        """Build prompt for French minutes generation"""
        return f"""
Analysez la transcription de réunion suivante et générez des comptes-rendus complets au format JSON.

TRANSCRIPTION:
{transcript_text}

Veuillez générer des comptes-rendus avec la structure suivante :
{{
    "summary": "Résumé exécutif brief de la réunion",
    "key_points": [
        "Points de discussion importants et décisions prises"
    ],
    "decisions": [
        {{
            "title": "Titre de la décision",
            "description": "Description détaillée de la décision",
            "made_by": "Personne ou groupe qui a pris la décision",
            "timestamp": "Heure approximative de la décision"
        }}
    ],
    "action_items": [
        {{
            "title": "Titre de l'action",
            "description": "Ce qui doit être fait",
            "assignee": "Personne responsable (si mentionnée)",
            "due_date": "Date d'échéance (si mentionnée)",
            "priority": "high/medium/low",
            "timestamp": "Quand cela a été assigné"
        }}
    ],
    "next_steps": [
        "Éléments de suivi et suggestions pour la prochaine réunion"
    ],
    "attendees": [
        "Liste des personnes qui ont participé"
    ]
}}

Directives importantes :
- Extrayez les informations réelles de la transcription, n'inventez pas de détails
- Incluez des horodatages pour les éléments clés (utilisez les temps approximatifs de la transcription)
- Marquez l'assigné comme null si non explicitement mentionné
- Utilisez des niveaux de priorité réalistes basés sur le contexte
- Assurez-vous que tout JSON est correctement formaté et valide
- Concentrez-vous sur les décisions concrètes et les éléments d'action
"""
    
    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from AI response when it's not pure JSON"""
        try:
            # Look for JSON block in response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                raise Exception("No JSON found in response")
                
        except Exception:
            # Return basic structure if parsing fails
            return {
                "summary": "AI processing failed - please review transcript manually",
                "key_points": [],
                "decisions": [],
                "action_items": [],
                "next_steps": [],
                "attendees": []
            }
    
    def _structure_minutes_data(self, ai_data: Dict[str, Any], transcript: Transcript, language: str) -> Dict[str, Any]:
        """Structure and validate AI-generated minutes data"""
        
        # Extract attendees from transcript
        attendees = set()
        for segment in transcript.segments.all():
            if segment.speaker:
                name = segment.speaker.display_name or segment.speaker.label
                attendees.add(name)
        
        # Structure the data
        structured_data = {
            "meeting_id": str(transcript.meeting.id),
            "meeting_title": transcript.meeting.title,
            "language": language,
            "generated_at": transcript.created_at.isoformat(),
            "summary": ai_data.get("summary", ""),
            "key_points": ai_data.get("key_points", []),
            "decisions": self._structure_decisions(ai_data.get("decisions", [])),
            "action_items": self._structure_action_items(ai_data.get("action_items", [])),
            "next_steps": ai_data.get("next_steps", []),
            "attendees": list(attendees),
            "transcript_id": str(transcript.id),
            "ai_model": self.model_name,
            "ai_version": self.model_version
        }
        
        return structured_data
    
    def _structure_decisions(self, decisions: List[Dict]) -> List[Dict]:
        """Structure decisions data"""
        structured_decisions = []
        
        for i, decision in enumerate(decisions):
            structured_decision = {
                "id": str(uuid.uuid4()),
                "title": decision.get("title", f"Decision {i+1}"),
                "description": decision.get("description", ""),
                "made_by": decision.get("made_by"),
                "timestamp": decision.get("timestamp"),
                "confidence": "high" if decision.get("title") and decision.get("description") else "medium"
            }
            structured_decisions.append(structured_decision)
        
        return structured_decisions
    
    def _structure_action_items(self, action_items: List[Dict]) -> List[Dict]:
        """Structure action items data"""
        structured_items = []
        
        for i, item in enumerate(action_items):
            structured_item = {
                "id": str(uuid.uuid4()),
                "title": item.get("title", f"Action Item {i+1}"),
                "description": item.get("description", ""),
                "assignee": item.get("assignee"),
                "due_date": item.get("due_date"),
                "priority": item.get("priority", "medium"),
                "timestamp": item.get("timestamp"),
                "status": "open",
                "confidence": "high" if item.get("title") and item.get("description") else "medium"
            }
            structured_items.append(structured_item)
        
        return structured_items
    
    def extract_action_items(self, minutes_data: Dict[str, Any], minutes: Minutes):
        """Extract and create action items from minutes data"""
        action_items_data = minutes_data.get("action_items", [])
        
        for item_data in action_items_data:
            # Find assignee user if mentioned
            assignee = None
            if item_data.get("assignee"):
                try:
                    from accounts.models import User
                    assignee = User.objects.filter(
                        email__icontains=item_data["assignee"].lower()
                    ).first()
                except:
                    pass
            
            # Create action item
            ActionItem.objects.create(
                meeting=minutes.meeting,
                minutes=minutes,
                title=item_data["title"],
                description=item_data["description"],
                assignee=assignee,
                due_date=item_data.get("due_date"),
                priority=item_data.get("priority", "medium"),
                source_segment_ids=[]  # Could be enhanced to track source segments
            )
    
    def convert_to_markdown(self, minutes_data: Dict[str, Any]) -> str:
        """Convert minutes data to markdown format"""
        language = minutes_data.get("language", "en")
        
        if language == "fr":
            return self._convert_to_french_markdown(minutes_data)
        else:
            return self._convert_to_english_markdown(minutes_data)
    
    def _convert_to_english_markdown(self, data: Dict[str, Any]) -> str:
        """Convert to English markdown"""
        md = []
        
        # Title and header
        md.append(f"# {data.get('meeting_title', 'Meeting Minutes')}")
        md.append(f"**Generated:** {data.get('generated_at', 'Unknown')}")
        md.append(f"**Language:** {data.get('language', 'en').upper()}")
        md.append("")
        
        # Summary
        if data.get("summary"):
            md.append("## Summary")
            md.append(data["summary"])
            md.append("")
        
        # Attendees
        if data.get("attendees"):
            md.append("## Attendees")
            for attendee in data["attendees"]:
                md.append(f"- {attendee}")
            md.append("")
        
        # Key Points
        if data.get("key_points"):
            md.append("## Key Points")
            for point in data["key_points"]:
                md.append(f"- {point}")
            md.append("")
        
        # Decisions
        if data.get("decisions"):
            md.append("## Decisions")
            for decision in data["decisions"]:
                md.append(f"### {decision['title']}")
                md.append(decision["description"])
                if decision.get("made_by"):
                    md.append(f"**Made by:** {decision['made_by']}")
                md.append("")
        
        # Action Items
        if data.get("action_items"):
            md.append("## Action Items")
            for item in data["action_items"]:
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(item.get("priority", "medium"), "🟡")
                md.append(f"### {priority_emoji} {item['title']}")
                md.append(item["description"])
                if item.get("assignee"):
                    md.append(f"**Assignee:** {item['assignee']}")
                if item.get("due_date"):
                    md.append(f"**Due:** {item['due_date']}")
                md.append("")
        
        # Next Steps
        if data.get("next_steps"):
            md.append("## Next Steps")
            for step in data["next_steps"]:
                md.append(f"- {step}")
            md.append("")
        
        return "\n".join(md)
    
    def _convert_to_french_markdown(self, data: Dict[str, Any]) -> str:
        """Convert to French markdown"""
        md = []
        
        # Title and header
        md.append(f"# {data.get('meeting_title', 'Compte-rendu de réunion')}")
        md.append(f"**Généré le:** {data.get('generated_at', 'Inconnu')}")
        md.append(f"**Langue:** {data.get('language', 'fr').upper()}")
        md.append("")
        
        # Summary
        if data.get("summary"):
            md.append("## Résumé")
            md.append(data["summary"])
            md.append("")
        
        # Attendees
        if data.get("attendees"):
            md.append("## Participants")
            for attendee in data["attendees"]:
                md.append(f"- {attendee}")
            md.append("")
        
        # Key Points
        if data.get("key_points"):
            md.append("## Points clés")
            for point in data["key_points"]:
                md.append(f"- {point}")
            md.append("")
        
        # Decisions
        if data.get("decisions"):
            md.append("## Décisions")
            for decision in data["decisions"]:
                md.append(f"### {decision['title']}")
                md.append(decision["description"])
                if decision.get("made_by"):
                    md.append(f"**Prise par:** {decision['made_by']}")
                md.append("")
        
        # Action Items
        if data.get("action_items"):
            md.append("## Éléments d'action")
            for item in data["action_items"]:
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(item.get("priority", "medium"), "🟡")
                md.append(f"### {priority_emoji} {item['title']}")
                md.append(item["description"])
                if item.get("assignee"):
                    md.append(f"**Responsable:** {item['assignee']}")
                if item.get("due_date"):
                    md.append(f"**Échéance:** {item['due_date']}")
                md.append("")
        
        # Next Steps
        if data.get("next_steps"):
            md.append("## Prochaines étapes")
            for step in data["next_steps"]:
                md.append(f"- {step}")
            md.append("")
        
        return "\n".join(md)