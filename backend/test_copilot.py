#!/usr/bin/env python
"""
Test script to verify Copilot models are working correctly.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meetin.settings')
django.setup()

from ai_copilot.models import CopilotSuggestion, CopilotRun, SpeakerUserMap
from meetings.models import Meeting
from accounts.models import User

def test_copilot_models():
    """Test Copilot models"""
    print("Testing Copilot models...")
    
    # Test creating a user
    user, created = User.objects.get_or_create(
        username='testuser',
        email='test@example.com',
        defaults={'password': 'testpass123'}
    )
    print(f"Created user: {user.email}")
    
    # Test creating a meeting
    meeting = Meeting.objects.create(
        title='Test Meeting',
        description='Test meeting for Copilot',
        language_preference='en',
        created_by=user
    )
    print(f"Created meeting: {meeting.title}")
    
    # Test creating a Copilot run
    run = CopilotRun.objects.create(
        meeting=meeting,
        mode='post_meeting',
        provider='openai',
        model='gpt-4',
        status='started'
    )
    print(f"Created Copilot run: {run.id}")
    
    # Test creating a suggestion
    suggestion = CopilotSuggestion.objects.create(
        meeting=meeting,
        type='action_item',
        payload_json={
            'title': 'Test Action Item',
            'description': 'Test description',
            'assignee': {'speaker_label': 'Speaker 1'},
            'priority': 'medium',
            'evidence': [
                {
                    'segment_id': 'test-segment-id',
                    'start_ms': 1000,
                    'end_ms': 2000,
                    'quote': 'Test quote'
                }
            ]
        },
        dedupe_key='test-key',
        source_segment_ids=['test-segment-id'],
        confidence=0.9
    )
    print(f"Created suggestion: {suggestion.type}")
    
    # Test creating a speaker mapping
    from meetings.models import Speaker
    speaker = Speaker.objects.create(
        meeting=meeting,
        label='Speaker 1'
    )
    
    mapping = SpeakerUserMap.objects.create(
        meeting=meeting,
        speaker=speaker,
        user=user,
        created_by=user
    )
    print(f"Created speaker mapping: {speaker.label} -> {user.email}")
    
    # Test querying
    suggestions = CopilotSuggestion.objects.filter(meeting=meeting)
    print(f"Found {suggestions.count()} suggestions for meeting")
    
    runs = CopilotRun.objects.filter(meeting=meeting)
    print(f"Found {runs.count()} runs for meeting")
    
    mappings = SpeakerUserMap.objects.filter(meeting=meeting)
    print(f"Found {mappings.count()} speaker mappings for meeting")
    
    print("\nAll Copilot models are working correctly!")
    return True

if __name__ == '__main__':
    try:
        test_copilot_models()
        print("\n✅ Copilot model test completed successfully!")
    except Exception as e:
        print(f"\nError testing Copilot models: {str(e)}")
        sys.exit(1)