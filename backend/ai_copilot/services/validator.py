import json
import re
from typing import Dict, List, Any, Optional, Tuple
from django.core.exceptions import ValidationError
from django.db import transaction
from ai_copilot.models import CopilotSuggestion, CopilotRun
from meetings.models import Meeting
from transcription.models import TranscriptSegment
import uuid
import logging

logger = logging.getLogger(__name__)


class CopilotValidator:
    """
    Validation layer for Copilot outputs with strict JSON schema enforcement.
    """
    
    # JSON schema for validation
    SCHEMA = {
        "type": "object",
        "required": ["language", "action_items", "decisions", "risks", "open_questions"],
        "properties": {
            "language": {"type": "string", "enum": ["en", "fr"]},
            "action_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["title", "description", "assignee", "priority", "evidence"],
                    "properties": {
                        "title": {"type": "string", "minLength": 1},
                        "description": {"type": "string", "minLength": 1},
                        "assignee": {
                            "type": "object",
                            "required": ["speaker_label"],
                            "properties": {
                                "speaker_label": {"type": "string"},
                                "user_id": {"type": ["string", "null"]},
                                "name": {"type": ["string", "null"]}
                            }
                        },
                        "due_date": {"type": ["string", "null"]},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                        "evidence": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "required": ["segment_id", "start_ms", "end_ms", "quote"],
                                "properties": {
                                    "segment_id": {"type": "string"},
                                    "start_ms": {"type": "integer"},
                                    "end_ms": {"type": "integer"},
                                    "quote": {"type": "string", "minLength": 1}
                                }
                            }
                        }
                    }
                }
            },
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["text", "evidence"],
                    "properties": {
                        "text": {"type": "string", "minLength": 1},
                        "evidence": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "required": ["segment_id", "start_ms", "end_ms", "quote"],
                                "properties": {
                                    "segment_id": {"type": "string"},
                                    "start_ms": {"type": "integer"},
                                    "end_ms": {"type": "integer"},
                                    "quote": {"type": "string", "minLength": 1}
                                }
                            }
                        }
                    }
                }
            },
            "risks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["text", "severity", "evidence"],
                    "properties": {
                        "text": {"type": "string", "minLength": 1},
                        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        "evidence": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "required": ["segment_id", "start_ms", "end_ms", "quote"],
                                "properties": {
                                    "segment_id": {"type": "string"},
                                    "start_ms": {"type": "integer"},
                                    "end_ms": {"type": "integer"},
                                    "quote": {"type": "string", "minLength": 1}
                                }
                            }
                        }
                    }
                }
            },
            "open_questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["text", "evidence"],
                    "properties": {
                        "text": {"type": "string", "minLength": 1},
                        "owner": {
                            "type": "object",
                            "properties": {
                                "speaker_label": {"type": "string"}
                            }
                        },
                        "evidence": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "required": ["segment_id", "start_ms", "end_ms", "quote"],
                                "properties": {
                                    "segment_id": {"type": "string"},
                                    "start_ms": {"type": "integer"},
                                    "end_ms": {"type": "integer"},
                                    "quote": {"type": "string", "minLength": 1}
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    @classmethod
    def validate_output(cls, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Copilot output against schema and business rules.
        
        Args:
            output: Raw LLM output dictionary
            
        Returns:
            Validated and sanitized output
            
        Raises:
            ValidationError: If output is invalid
        """
        try:
            # Basic schema validation
            cls._validate_schema(output)
            
            # Business rule validation
            cls._validate_business_rules(output)
            
            # Sanitize output
            sanitized = cls._sanitize_output(output)
            
            return sanitized
            
        except Exception as e:
            logger.error(f"Copilot validation failed: {str(e)}")
            raise ValidationError(f"Invalid Copilot output: {str(e)}")
    
    @classmethod
    def _validate_schema(cls, output: Dict[str, Any]) -> None:
        """Validate output against JSON schema"""
        # Check required fields
        required_fields = ["language", "action_items", "decisions", "risks", "open_questions"]
        for field in required_fields:
            if field not in output:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate language
        if output["language"] not in ["en", "fr"]:
            raise ValidationError("Invalid language. Must be 'en' or 'fr'")
        
        # Validate each array contains proper objects
        for array_name in ["action_items", "decisions", "risks", "open_questions"]:
            if not isinstance(output[array_name], list):
                raise ValidationError(f"Field {array_name} must be an array")
            
            for i, item in enumerate(output[array_name]):
                cls._validate_item(item, array_name, i)
    
    @classmethod
    def _validate_item(cls, item: Dict[str, Any], item_type: str, index: int) -> None:
        """Validate individual item based on type"""
        if item_type == "action_items":
            cls._validate_action_item(item, index)
        elif item_type == "decisions":
            cls._validate_decision(item, index)
        elif item_type == "risks":
            cls._validate_risk(item, index)
        elif item_type == "open_questions":
            cls._validate_question(item, index)
    
    @classmethod
    def _validate_action_item(cls, item: Dict[str, Any], index: int) -> None:
        """Validate action item"""
        required_fields = ["title", "description", "assignee", "priority", "evidence"]
        for field in required_fields:
            if field not in item:
                raise ValidationError(f"Action item {index} missing required field: {field}")
        
        # Validate assignee
        if not isinstance(item["assignee"], dict) or "speaker_label" not in item["assignee"]:
            raise ValidationError(f"Action item {index} has invalid assignee")
        
        # Validate priority
        if item["priority"] not in ["low", "medium", "high"]:
            raise ValidationError(f"Action item {index} has invalid priority")
        
        # Validate evidence
        cls._validate_evidence(item["evidence"], f"action item {index}")
    
    @classmethod
    def _validate_decision(cls, item: Dict[str, Any], index: int) -> None:
        """Validate decision"""
        required_fields = ["text", "evidence"]
        for field in required_fields:
            if field not in item:
                raise ValidationError(f"Decision {index} missing required field: {field}")
        
        cls._validate_evidence(item["evidence"], f"decision {index}")
    
    @classmethod
    def _validate_risk(cls, item: Dict[str, Any], index: int) -> None:
        """Validate risk"""
        required_fields = ["text", "severity", "evidence"]
        for field in required_fields:
            if field not in item:
                raise ValidationError(f"Risk {index} missing required field: {field}")
        
        if item["severity"] not in ["low", "medium", "high"]:
            raise ValidationError(f"Risk {index} has invalid severity")
        
        cls._validate_evidence(item["evidence"], f"risk {index}")
    
    @classmethod
    def _validate_question(cls, item: Dict[str, Any], index: int) -> None:
        """Validate open question"""
        required_fields = ["text", "evidence"]
        for field in required_fields:
            if field not in item:
                raise ValidationError(f"Question {index} missing required field: {field}")
        
        cls._validate_evidence(item["evidence"], f"question {index}")
    
    @classmethod
    def _validate_evidence(cls, evidence: List[Dict[str, Any]], context: str) -> None:
        """Validate evidence array"""
        if not isinstance(evidence, list) or len(evidence) == 0:
            raise ValidationError(f"{context} must have at least one evidence item")
        
        for i, ev in enumerate(evidence):
            required_fields = ["segment_id", "start_ms", "end_ms", "quote"]
            for field in required_fields:
                if field not in ev:
                    raise ValidationError(f"{context} evidence {i} missing required field: {field}")
            
            # Validate timing
            if not isinstance(ev["start_ms"], int) or not isinstance(ev["end_ms"], int):
                raise ValidationError(f"{context} evidence {i} has invalid timing")
            
            if ev["start_ms"] >= ev["end_ms"]:
                raise ValidationError(f"{context} evidence {i} has invalid time range")
            
            # Validate quote
            if not isinstance(ev["quote"], str) or len(ev["quote"].strip()) == 0:
                raise ValidationError(f"{context} evidence {i} has invalid quote")
    
    @classmethod
    def _validate_business_rules(cls, output: Dict[str, Any]) -> None:
        """Validate business rules"""
        # Check for duplicate titles within same type
        for item_type in ["action_items", "decisions", "risks", "open_questions"]:
            titles = [item.get("title", "").lower() for item in output[item_type]]
            if len(titles) != len(set(titles)):
                raise ValidationError(f"Duplicate titles found in {item_type}")
        
        # Validate evidence segment IDs exist (would need database check)
        # This is handled during suggestion creation
    
    @classmethod
    def _sanitize_output(cls, output: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize output by removing extra fields and normalizing"""
        sanitized = {
            "language": output["language"],
            "action_items": [],
            "decisions": [],
            "risks": [],
            "open_questions": []
        }
        
        # Copy and sanitize each item type
        for item_type in ["action_items", "decisions", "risks", "open_questions"]:
            for item in output[item_type]:
                sanitized_item = cls._sanitize_item(item, item_type)
                sanitized[item_type].append(sanitized_item)
        
        return sanitized
    
    @classmethod
    def _sanitize_item(cls, item: Dict[str, Any], item_type: str) -> Dict[str, Any]:
        """Sanitize individual item"""
        # Define allowed fields for each type
        if item_type == "action_items":
            allowed_fields = ["title", "description", "assignee", "due_date", "priority", "evidence"]
        elif item_type == "decisions":
            allowed_fields = ["text", "evidence"]
        elif item_type == "risks":
            allowed_fields = ["text", "severity", "evidence"]
        else:  # open_questions
            allowed_fields = ["text", "owner", "evidence"]
        
        sanitized = {}
        for field in allowed_fields:
            if field in item:
                sanitized[field] = item[field]
        
        return sanitized


class CopilotDeduplicator:
    """
    Deduplication and merge engine for Copilot suggestions.
    """
    
    @staticmethod
    def generate_dedupe_key(item: Dict[str, Any], item_type: str, meeting_id: str) -> str:
        """
        Generate stable deduplication key for an item.
        
        Args:
            item: Item dictionary
            item_type: Type of item (action_item, decision, etc.)
            meeting_id: Meeting ID for context
            
        Returns:
            Stable deduplication key
        """
        # Normalize text for comparison
        if item_type == "action_items":
            text = f"{item.get('title', '')} {item.get('description', '')}"
        else:
            text = item.get('text', '')
        
        # Remove punctuation, lowercase, remove extra spaces
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Create key
        key = f"{meeting_id}:{item_type}:{normalized[:100]}"  # Limit length
        
        return key
    
    @staticmethod
    def calculate_similarity(item1: Dict[str, Any], item2: Dict[str, Any], item_type: str) -> float:
        """
        Calculate similarity between two items (0.0 to 1.0).
        
        Args:
            item1, item2: Items to compare
            item_type: Type of items
            
        Returns:
            Similarity score
        """
        if item_type == "action_items":
            # Compare title and description
            text1 = f"{item1.get('title', '')} {item1.get('description', '')}"
            text2 = f"{item2.get('title', '')} {item2.get('description', '')}"
        else:
            text1 = item1.get('text', '')
            text2 = item2.get('text', '')
        
        # Simple text similarity (could be enhanced with embeddings)
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    @staticmethod
    @transaction.atomic
    def merge_or_create_suggestions(
        meeting: Meeting, 
        new_items: Dict[str, List[Dict[str, Any]]],
        copilot_run: CopilotRun
    ) -> List[CopilotSuggestion]:
        """
        Merge new items with existing suggestions or create new ones.
        
        Args:
            meeting: Meeting object
            new_items: New items from LLM output
            copilot_run: Copilot run for tracking
            
        Returns:
            List of created/updated suggestions
        """
        created_suggestions = []
        
        # Get existing suggestions for this meeting
        existing_suggestions = CopilotSuggestion.objects.filter(
            meeting=meeting,
            status__in=[CopilotSuggestion.SuggestionStatus.PROPOSED, CopilotSuggestion.SuggestionStatus.EDITED]
        )
        
        # Create lookup by dedupe key
        existing_by_key = {}
        for suggestion in existing_suggestions:
            existing_by_key[suggestion.dedupe_key] = suggestion
        
        # Process each item type
        for item_type, items in new_items.items():
            for item in items:
                # Generate dedupe key
                dedupe_key = CopilotDeduplicator.generate_dedupe_key(
                    item, item_type, str(meeting.id)
                )
                
                # Check for existing suggestion
                existing = existing_by_key.get(dedupe_key)
                
                if existing:
                    # Merge with existing
                    merged_suggestion = CopilotDeduplicator._merge_suggestion(
                        existing, item, dedupe_key
                    )
                    created_suggestions.append(merged_suggestion)
                else:
                    # Create new suggestion
                    new_suggestion = CopilotDeduplicator._create_suggestion(
                        meeting, item_type, item, dedupe_key, copilot_run
                    )
                    created_suggestions.append(new_suggestion)
        
        return created_suggestions
    
    @staticmethod
    def _merge_suggestion(
        existing: CopilotSuggestion, 
        new_item: Dict[str, Any], 
        dedupe_key: str
    ) -> CopilotSuggestion:
        """Merge new item with existing suggestion"""
        # Merge evidence
        existing_evidence = existing.payload_json.get('evidence', [])
        new_evidence = new_item.get('evidence', [])
        
        # Combine evidence, avoiding duplicates
        combined_evidence = existing_evidence.copy()
        for ev in new_evidence:
            if ev not in combined_evidence:
                combined_evidence.append(ev)
        
        # Update payload
        updated_payload = existing.payload_json.copy()
        updated_payload.update(new_item)
        updated_payload['evidence'] = combined_evidence
        
        # Update suggestion
        existing.payload_json = updated_payload
        existing.updated_at = timezone.now()
        existing.save()
        
        return existing
    
    @staticmethod
    def _create_suggestion(
        meeting: Meeting,
        item_type: str,
        item: Dict[str, Any],
        dedupe_key: str,
        copilot_run: CopilotRun
    ) -> CopilotSuggestion:
        """Create new suggestion from item"""
        # Extract source segment IDs from evidence
        source_segment_ids = []
        for evidence in item.get('evidence', []):
            if 'segment_id' in evidence:
                source_segment_ids.append(evidence['segment_id'])
        
        # Create suggestion
        suggestion = CopilotSuggestion.objects.create(
            meeting=meeting,
            type=item_type,
            payload_json=item,
            dedupe_key=dedupe_key,
            source_segment_ids=source_segment_ids,
            confidence=item.get('confidence', 0.8),
            created_by='ai'
        )
        
        return suggestion