import json
import logging
import os
import re
import requests
from django.conf import settings
from asgiref.sync import sync_to_async
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Ollama/Gemma API endpoint
GEMMA_API = getattr(settings, "GEMMA_API", "http://localhost:11434/api/generate")
PROMPT_DIR = os.path.join(settings.BASE_DIR, "chatbot", "prompts")
CRISIS_KEYWORDS_FILE = os.path.join(PROMPT_DIR, "crisis_keywords.txt")

# Cache for prompts to avoid file reading on every request
prompt_cache = {}
cache_last_updated = {}

def get_cached_prompt(filename):
    """Get prompt from cache or file with automatic refresh"""
    filepath = os.path.join(PROMPT_DIR, filename)
    
    # Check if cache needs refresh (every 5 minutes)
    current_time = datetime.now()
    if (filename not in cache_last_updated or 
        current_time - cache_last_updated[filename] > timedelta(minutes=5) or
        filename not in prompt_cache):
        
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                prompt_cache[filename] = file.read().strip()
            cache_last_updated[filename] = current_time
        except Exception as e:
            logger.error(f"Failed to load prompt file {filename}: {e}")
            return ""
    
    return prompt_cache[filename]

def load_prompts(username, conversation, user_context=""):
    """Load and combine all prompt sections efficiently with user context"""
    files = ["identity.txt", "personalization.txt", "rules.txt",
             "style.txt", "knowledge.txt", "user_context.txt", "safety.txt", "memory.txt"]
         
    prompt_sections = []
    for f in files:
        text = get_cached_prompt(f)
        if text:
            # Replace placeholders
            text = text.replace("{username}", username)
            text = text.replace("{conversation}", conversation)
            text = text.replace("{user_context}", user_context)
            prompt_sections.append(text)
         
    return "\n\n".join(prompt_sections)

def check_crisis(user_message: str) -> tuple:
    """
    Detect if a message contains suicidal or crisis intent using a tiered scoring system.
    Returns a tuple of (is_crisis, score, triggered_keywords)
    """
    # Define keyword categories with different weights
    keyword_categories = {
    "direct_intent": {
        "weight": 10,
        "keywords": [
            "i want to die", "i wanna die", "i want to kill myself", "i wanna kill myself",
            "i'm going to kill myself", "gonna kill myself", "i will kill myself",
            "plan to kill myself", "going to end it all", "end my life", "take my own life",
            "commit suicide", "kill myself", "ending my life", "want to commit suicide",
            "thinking of suicide", "suicidal thoughts", "feeling suicidal",
            "have suicidal thoughts", "ready to die", "time to die", "should just die",
            "better off dead", "better off without me", "world is better without me",
            "i am a burden", "no one would miss me", "disappear forever", "make it all stop",
            "make the pain stop", "end the pain", "stop the pain", "permanent solution",
            "final solution", "final escape", "give up on life", "tired of living",
            "don't want to be here", "don't wanna be here", "want to disappear",
            "want to be dead", "wish i was dead", "wish i were dead", "not meant for this world",
            "quit life"
        ]
    },
    "methods": {
        "weight": 9,
        "keywords": [
            "how to kill myself", "how to commit suicide", "best way to kill myself",
            "easy way to die", "painless suicide", "quick way out", "ways to die",
            "how to hang myself", "hanging myself", "tie a noose", "jump off a bridge",
            "jump from a building", "jump in front of a train", "jump in front of traffic",
            "step in front of a bus", "train track", "subway track", "overdose on pills",
            "pill overdose", "take all my pills", "OD on pills", "carbon monoxide poisoning",
            "car in garage", "exhaust fumes", "cut my wrists", "slit my wrists", "bleed out",
            "shot myself", "gun to my head", "use a gun", "asphyxiation", "suffocation",
            "plastic bag", "drink poison", "rat poison", "cyanide"
        ]
    },
    "self_harm": {
        "weight": 7,
        "keywords": [
            "self harm", "self harm myself", "hurt myself", "cut myself", "cutting myself",
            "burn myself", "burning myself", "self injury", "self injure", "self mutilation",
            "self mutilate", "punish myself", "feel something", "feel pain", "physical pain",
            "emotional pain", "see blood", "bleeding to cope", "relief from cutting",
            "starve myself", "not eating", "not sleeping", "isolation", "isolate myself",
            "self sabotage", "self destructive", "self hatred", "self loathing"
        ]
    },
    "emotional": {
        "weight": 5,
        "keywords": [
            "hopeless", "helpless", "worthless", "nothing matters", "pointless", "no point",
            "no future", "no hope", "can't see a future", "empty inside", "numb", "drowning",
            "sinking feeling", "crushing despair", "deep depression", "severe depression",
            "unbearable pain", "mental pain", "psychological pain", "too much to bear",
            "can't cope anymore", "can't deal with this", "can't go on", "can't take it",
            "can't do this", "overwhelmed", "broken", "shattered", "lost cause", "failure",
            "complete failure", "alone", "utterly alone", "lonely", "isolated", "misunderstood",
            "trapped", "stuck", "no way out", "no escape", "no exit", "darkness", "dark thoughts",
            "intrusive thoughts", "the voice tells me", "the thoughts are back", "relapse of thoughts",
            "urges to hurt myself", "suicidal urge", "triggered"
        ]
    },
    "goodbye": {
        "weight": 8,
        "keywords": [
            "goodbye forever", "final goodbye", "last post", "last message", "last words",
            "this is the end", "if i don't see you", "if this is my last", "sorry for everything",
            "forgive me", "you'll be better off", "i love you all", "take care of", "my will",
            "who gets my things", "giving away my stuff", "cleaning my room", "settling affairs"
        ]
    },
    "slang": {
        "weight": 6,
        "keywords": [
            "kms", "kys", "unalive", "unalive myself", "delete myself", "ctb", "sh", "end it",
            "yeet myself", "off myself", "game over", "press quit", "log off forever",
            "permanent sleep", "eternal sleep", "never wake up", "go to sleep forever",
            "see the reaper", "meet the reaper", "dance with death", "embrace the void",
            "join the void", "fade to black", "black hole", "curtain call", "final rest",
            "check out early", "buy the farm", "bite the bullet", "cash in my chips"
        ]
    }
}
    
    # Try to load keywords from file if it exists
    try:
        with open(CRISIS_KEYWORDS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Parse the file content to extract keywords by category
        current_category = None
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('#') and ':' in line:
                # This is a category heading
                category_name = line.split('#')[-1].split(':')[0].strip().lower().replace(' ', '_')
                if category_name in keyword_categories:
                    current_category = category_name
            elif line and not line.startswith('#') and current_category:
                # Add keyword to the appropriate category
                keyword = line.split('#')[0].strip()
                if keyword and keyword not in keyword_categories[current_category]["keywords"]:
                    keyword_categories[current_category]["keywords"].append(keyword)
    except Exception as e:
        logger.error(f"Failed to load crisis keywords file: {e}")
        # Fallback to essential keywords
        keyword_categories["direct_intent"]["keywords"] = [
            "suicide", "kill myself", "end my life", "ending my life",
            "i want to die", "i give up", "commit suicide", "take my own life"
        ]
    
    text = user_message.lower().strip()
    score = 0
    triggered_keywords = []
    
    # Check each category
    for category, data in keyword_categories.items():
        for keyword in data["keywords"]:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text):
                score += data["weight"]
                triggered_keywords.append(keyword)
    
    # Determine if it's a crisis based on thresholds
    is_crisis = score >= 15 or any(
        re.search(r'\b' + re.escape(phrase) + r'\b', text) 
        for phrase in ["kill myself", "suicide", "end my life", "want to die"]
    )
    
    return (is_crisis, score, triggered_keywords)

def summarize_with_gemma(conversation_text):
    """
    Use Gemma API to generate intelligent conversation summaries.
    """
    summary_prompt = f"""
Please provide a concise summary of the following conversation for memory purposes.
Focus on key topics, emotions, and important details mentioned by the user.
Keep it brief but informative (2-3 sentences maximum).

Conversation:
{conversation_text}

Summary:
"""
    
    payload = {
        "model": "gemma3:12b",
        "prompt": summary_prompt,
        "stream": False,
        "max_tokens": 100,
        "temperature": 0.3,
    }
    
    try:
        response = requests.post(GEMMA_API, json=payload, timeout=80)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()
    except Exception as e:
        logger.error(f"Failed to generate summary with Gemma: {e}")
        # Fallback to truncation
        if len(conversation_text) > 500:
            return conversation_text[:500] + "... (truncated)"
        return conversation_text

def summarize_memory(messages):
    """
    Summarize old messages into a short memory note using Gemma AI.
    """
    if not messages:
        return "No previous conversation."
    
    conversation_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
    
    # If conversation is very short, just return it as is
    if len(conversation_text) <= 300:
        return f"Previous conversation:\n{conversation_text}"
    
    # Use AI for longer conversations
    ai_summary = summarize_with_gemma(conversation_text)
    return f"Conversation summary: {ai_summary}"

def build_hybrid_memory(chat_session, user_message, limit=5):
    """
    Build prompt with long-term memory + recent conversation.
    """
    memory = chat_session.memory or ""

    # Short-term memory: last N messages
    history = chat_session.conversation[-limit:] if chat_session.conversation else []

    recent_convo = []
    for msg in history:
        role = "User" if msg["role"] == "user" else "Luna"
        recent_convo.append(f"{role}: {msg['content']}")

    # Add the new user message at the end
    recent_convo.append(f"User: {user_message}")

    return f"{memory}\n\n" + "\n".join(recent_convo)

async def update_long_term_memory_async(chat_session, threshold=20, summarize_count=15):
    """
    Async version to update long-term memory without blocking.
    """
    if len(chat_session.conversation) > threshold:
        old_messages = chat_session.conversation[:summarize_count]
        
        # Run summarization in background task
        asyncio.create_task(background_summarization(chat_session, old_messages))
        
        # Immediately trim conversation without waiting for summary
        chat_session.conversation = chat_session.conversation[summarize_count:]
        await sync_to_async(chat_session.save)(update_fields=["conversation", "updated_at"])

async def background_summarization(chat_session, old_messages):
    """Background task for AI summarization"""
    try:
        summary = await sync_to_async(summarize_memory)(old_messages)
        
        # Update memory when summary is ready
        if chat_session.memory:
            new_memory = f"{chat_session.memory}\n\n{summary}"
        else:
            new_memory = summary
        
        # Update the session safely
        chat_session.memory = new_memory
        await sync_to_async(chat_session.save)(update_fields=["memory"])
        
    except Exception as e:
        logger.error(f"Background summarization failed: {e}")

# Sync version for compatibility
def update_long_term_memory(chat_session, threshold=20, summarize_count=15):
    """
    Periodically summarize old messages into long-term memory.
    """
    if len(chat_session.conversation) > threshold:
        old_messages = chat_session.conversation[:summarize_count]

        # Summarize
        summary = summarize_memory(old_messages)
        chat_session.memory = (chat_session.memory or "") + "\n" + summary

        # Keep only the remaining messages
        chat_session.conversation = chat_session.conversation[summarize_count:]
        chat_session.save(update_fields=["conversation", "memory", "updated_at"])




import json
import logging

logger = logging.getLogger(__name__)

# Valid frontend routes
VALID_URLS = ["/", "/dashboard", "/profile", "/settings"]  # extend as needed

def parse_gemma_response(gemma_text):
    """Try to extract JSON command from Gemma, fallback to text only."""
    try:
        print(f"[DEBUG] Parsing Gemma response: {gemma_text}")  # debug
        data = json.loads(gemma_text)
        if "text" in data:
            target = data.get("target")
            if target and target not in VALID_URLS:
                print(f"[DEBUG] Invalid redirect target from Gemma: {target}")  # debug
                logger.warning(f"Invalid redirect target from Gemma: {target}")
                data["action"] = None
                data["target"] = None
                data["text"] += "\n(Note: I couldn’t find that page. Please try again.)"
            return data
    except Exception as e:
        print(f"[DEBUG] Failed to parse Gemma JSON, fallback to text. Error: {e}")  # debug
        logger.warning(f"Failed to parse Gemma JSON: {e}")
    return {"text": gemma_text}


from chatbot.models import UserData  # adjust import if needed

def handle_user_command(command: str, chat_session):
    command = command.lower().strip()
    print(f"[DEBUG] Handling user command: {command}")  # debug

    # CLEAR MEMORY & HISTORY + DELETE USER DATA
    if command in ["clear memory", "clear all memory", "clear all your memory and history", "claer all my history data","delete data and history","clear data"]:
        try:
            # clear chat session memory
            chat_session.clear_memory()

            # delete user data linked to this user
            if chat_session.user:  # make sure a user exists
                deleted_count, _ = UserData.objects.filter(user=chat_session.user).delete()
                print(f"[DEBUG] Deleted {deleted_count} user data rows for {chat_session.user.username}")

            print("[DEBUG] Cleared all memory, history, and user data.")  # debug
            return {"text": "All memory, history, and stored user data have been cleared. ✅"}, True
        except Exception as e:
            print(f"[DEBUG] Error clearing memory/user data: {e}")  # debug
            logger.error(f"Error clearing memory/user data: {e}")
            return {"text": "Failed to clear memory and user data. ❌"}, True

    # START OVER (only clears chat, not user data)
    if command in ["start over", "restart chat"]:
        try:    
            chat_session.conversation = []
            chat_session.save(update_fields=["conversation"])
            print("[DEBUG] Chat restarted.")  # debug
            return {"text": "Chat restarted. You can start fresh! 🌱"}, True
        except Exception as e:
            print(f"[DEBUG] Error restarting chat: {e}")  # debug
            logger.error(f"Error restarting chat: {e}")
            return {"text": "Failed to restart chat. ❌"}, True

    # Example static redirects
    STATIC_COMMANDS = {
        "go to home": {"text": "Redirecting you to Home...", "action": "redirect", "target": "/", "delay": 5},
        "go to dashboard": {"text": "Redirecting you to Dashboard...", "action": "redirect", "target": "/dashboard", "delay": 5},
        "go to profile": {"text": "Redirecting you to Profile...", "action": "redirect", "target": "/profile", "delay": 5},
    }

    if command in STATIC_COMMANDS:
        print(f"[DEBUG] Static command matched: {command}")  # debug
        return STATIC_COMMANDS[command], True

    print("[DEBUG] No command matched")  # debug
    return {}, False








import json
import re
import requests
from django.conf import settings
from .models import UserData
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Gemma API endpoint
GEMMA_API = getattr(settings, 'GEMMA_API', 'http://localhost:11434/api/generate')

def calculate_string_similarity(a, b):
    """Calculate similarity between two strings using SequenceMatcher"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_similar_keys_multilayer(new_key, existing_keys, user):
    """
    Use multiple approaches to find similar keys:
    1. String similarity matching
    2. AI-powered semantic matching
    3. Concept extraction matching
    Returns: existing key that should be used, or None if no match
    """
    if not existing_keys:
        return None
    
    new_key_lower = new_key.lower()
    
    # Layer 1: High string similarity (fast check)
    for existing_key in existing_keys:
        similarity = calculate_string_similarity(new_key, existing_key)
        if similarity > 0.8:  # Very similar strings
            logger.info(f"String similarity match: '{new_key}' -> '{existing_key}' (similarity: {similarity:.2f})")
            return existing_key
    
    # Layer 2: Concept-based matching (medium speed)
    concept_matches = find_concept_matches(new_key, existing_keys)
    if concept_matches:
        logger.info(f"Concept match found: '{new_key}' -> '{concept_matches[0]}'")
        return concept_matches[0]
    
    # Layer 3: AI semantic matching (slower, but most accurate)
    ai_match = find_similar_keys_with_ai(new_key, existing_keys, user)
    if ai_match:
        logger.info(f"AI semantic match: '{new_key}' -> '{ai_match}'")
        return ai_match
    
    return None

def find_concept_matches(new_key, existing_keys):
    """
    Find matches based on key concepts/words
    Returns: list of matching keys
    """
    # Extract meaningful words from the new key
    new_words = set(re.findall(r'\w+', new_key.lower()))
    
    # Common concept groups
    concept_groups = {
        'partner': {'spouse', 'wife', 'husband', 'partner', 'girlfriend', 'boyfriend'},
        'weight': {'weight', 'pounds', 'lbs', 'kg', 'kilos', 'mass'},
        'height': {'height', 'tall', 'feet', 'ft', 'inches', 'cm', 'centimeters'},
        'age': {'age', 'years', 'old', 'born', 'birthday'},
        'location': {'city', 'state', 'country', 'address', 'live', 'from'},
        'name': {'name', 'called', 'first', 'last', 'full'},
        'work': {'job', 'work', 'occupation', 'career', 'employer', 'company'},
        'pet': {'pet', 'dog', 'cat', 'animal'},
        'child': {'child', 'kid', 'son', 'daughter', 'children'},
        'color': {'color', 'favourite', 'favorite'},
        'hobby': {'hobby', 'like', 'enjoy', 'interest'}
    }
    
    matches = []
    
    for existing_key in existing_keys:
        existing_words = set(re.findall(r'\w+', existing_key.lower()))
        
        # Direct word overlap
        common_words = new_words.intersection(existing_words)
        if common_words and len(common_words) >= 1:
            # Check if they share important concept words
            for concept, concept_words in concept_groups.items():
                if (new_words.intersection(concept_words) and 
                    existing_words.intersection(concept_words)):
                    matches.append(existing_key)
                    break
    
    return matches

def find_similar_keys_with_ai(new_key, existing_keys, user):
    """
    Use AI to find if a new key is similar to existing keys
    Returns: existing key that should be used, or None if no match
    """
    if not existing_keys or len(existing_keys) > 10:  # Limit AI calls for performance
        return None
    
    # Create a more focused prompt
    prompt = f"""
Compare these data keys to see if they refer to the same personal information:

New key: "{new_key}"
Existing keys: {existing_keys[:10]}  

Examples of SAME concept:
- "wife_name" and "spouse_name" = SAME (both refer to partner's name)
- "weight_lbs" and "weight_kg" = SAME (both refer to body weight)
- "age" and "age_years" = SAME (both refer to person's age)
- "favorite_color" and "preferred_color" = SAME (both refer to color preference)

Examples of DIFFERENT concept:
- "wife_name" and "child_name" = DIFFERENT
- "weight" and "height" = DIFFERENT
- "work_address" and "home_address" = DIFFERENT

Return ONLY this JSON:
{{"match": "existing_key_if_same_or_null", "confidence": 0.0-1.0}}
"""

    try:
        payload = {
            "model": "gemma3:12b",
            "prompt": prompt,
            "stream": False,
            "max_tokens": 100,
            "temperature": 0.05,  # Very low temperature for consistency
            "format": "json"
        }

        response = requests.post(GEMMA_API, json=payload, timeout=80)
        response.raise_for_status()
        
        ai_response = response.json().get('response', '')
        
        try:
            result = json.loads(ai_response)
            match = result.get('match')
            confidence = result.get('confidence', 0)
            
            if match and match != "null" and confidence > 0.75:
                return match
                
        except json.JSONDecodeError:
            logger.debug(f"AI response parsing failed: {ai_response}")
            
    except Exception as e:
        logger.error(f"AI key matching failed: {str(e)}")
    
    return None

def extract_user_data_with_ai(user_message, user, chat_session):
    """
    Use Gemma AI to extract structured user data from a message
    Returns: dict with extracted data or None if no data found
    """
    extraction_prompt = f"""
Extract personal information from this message. Be very specific with key names.

Message: "{user_message}"

Return ONLY valid JSON:
{{
    "extracted_data": {{
        "specific_key": {{"value": "exact_value", "type": "string|number", "confidence": 0.8}}
    }},
    "has_data": true|false
}}

Key naming rules:
- Use descriptive names: "partner_name", "weight_lbs", "age_years"
- Include units: "height_feet", "weight_kg" 
- Be specific: "favorite_food" not just "food"
- Use underscores: "birth_date" not "birth date"

Only extract if you're confident (>0.7). Return "has_data": false if unsure.
"""

    try:
        payload = {
            "model": "gemma3:12b",
            "prompt": extraction_prompt,
            "stream": False,
            "max_tokens": 400,
            "temperature": 0.2,
            "format": "json"
        }

        logger.info(f"Extracting user data from: {user_message[:100]}...")
        response = requests.post(GEMMA_API, json=payload, timeout=85)
        response.raise_for_status()
        
        ai_response = response.json().get('response', '')
        logger.debug(f"AI extraction response: {ai_response}")
        
        try:
            extraction_result = json.loads(ai_response)
        except json.JSONDecodeError:
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                extraction_result = json.loads(json_match.group())
            else:
                logger.debug("No valid JSON found in AI response")
                return None

        if extraction_result.get('has_data', False):
            extracted_data = extraction_result.get('extracted_data', {})
            saved_data = {}
            
            # Get existing keys for this user
            existing_keys = list(UserData.objects.filter(user=user).values_list('key', flat=True))
            
            for key, data_info in extracted_data.items():
                if isinstance(data_info, dict) and 'value' in data_info:
                    # Use multi-layer matching to find similar keys
                    similar_key = find_similar_keys_multilayer(key, existing_keys, user)
                    final_key = similar_key if similar_key else key
                    
                    if similar_key:
                        logger.info(f"MERGED: Using existing key '{similar_key}' instead of '{key}'")
                    else:
                        logger.info(f"NEW: Creating new key '{key}'")
                    
                    saved_data[final_key] = save_user_data(
                        user=user,
                        key=final_key,
                        value=str(data_info['value']),
                        data_type=data_info.get('type', 'string'),
                        confidence_score=data_info.get('confidence', 0.8),
                        source_message=user_message
                    )
            
            logger.info(f"Extracted and saved {len(saved_data)} data points")
            return saved_data
            
    except Exception as e:
        logger.error(f"User data extraction failed: {str(e)}")
    
    return None

def save_user_data(user, key, value, data_type='string', confidence_score=1.0, source_message=None):
    """
    Save or update user data in the database
    Returns: UserData object
    """
    try:
        logger.debug(f"Attempting to save user data: {key} = {value} (type: {data_type})")
        
        user_data, created = UserData.objects.get_or_create(
            user=user,
            key=key,
            defaults={
                'value': value,
                'data_type': data_type,
                'confidence_score': confidence_score,
                'source_message': source_message
            }
        )
        
        if not created:
            old_value = user_data.value
            
            if old_value != value:
                user_data.value = value
                user_data.data_type = data_type
                user_data.confidence_score = confidence_score
                user_data.source_message = source_message
                user_data.save(update_fields=['value', 'data_type', 'confidence_score', 'source_message', 'updated_at'])
                
                logger.info(f"✅ UPDATED: {key} = '{old_value}' -> '{value}'")
            else:
                logger.debug(f"⚪ UNCHANGED: {key} = '{value}'")
        else:
            logger.info(f"🆕 CREATED: {key} = '{value}'")
        
        return user_data
        
    except Exception as e:
        logger.error(f"❌ FAILED to save {key}={value}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_user_data(user, key=None):
    """
    Retrieve user data from database
    Returns: UserData object, dict of all data, or None
    """
    try:
        if key:
            return UserData.objects.get(user=user, key=key)
        else:
            user_data = UserData.objects.filter(user=user).values('key', 'value', 'data_type', 'updated_at')
            return {item['key']: item for item in user_data}
    except UserData.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Failed to get user data: {str(e)}")
        return None

def build_user_context(user, max_items=20):
    """
    Build a context string with user's personal data for AI prompts
    Returns: string with user context
    """
    try:
        user_data = UserData.objects.filter(user=user).order_by('-updated_at')[:max_items]
        
        if not user_data.exists():
            return ""
        
        context_parts = ["=== User Personal Information ==="]
        for data in user_data:
            readable_key = data.key.replace('_', ' ').title()
            context_parts.append(f"- {readable_key}: {data.value}")
        
        context_parts.append("=== End User Information ===\n")
        return "\n".join(context_parts)
        
    except Exception as e:
        logger.error(f"Failed to build user context: {str(e)}")
        return ""

def should_extract_data(user_message):
    """
    Quick check to see if message likely contains extractable user data
    Returns: boolean
    """
    data_indicators = [
        'my', 'i am', 'i\'m', 'i like', 'i love', 'i hate', 'i prefer',
        'my name is', 'i weigh', 'i weight', 'years old', 'born in',
        'live in', 'from', 'my favorite', 'i work', 'i study',
        'my height', 'my age', 'i have', 'i own', 'my pet',
        'my family', 'married', 'single', 'divorced', 'my job'
    ]
    
    message_lower = user_message.lower()
    has_indicators = any(indicator in message_lower for indicator in data_indicators)
    has_length = len(user_message.split()) >= 3
    
    return has_indicators and has_length

def cleanup_duplicate_keys(user):
    """
    Clean up existing duplicate keys using the multi-layer approach
    """
    try:
        user_data_entries = UserData.objects.filter(user=user).order_by('created_at')
        if user_data_entries.count() < 2:
            return
        
        keys_processed = set()
        merged_count = 0
        
        for entry in user_data_entries:
            if entry.key in keys_processed:
                continue
                
            # Get all remaining keys
            remaining_keys = list(
                user_data_entries.exclude(key__in=keys_processed)
                .exclude(key=entry.key)
                .values_list('key', flat=True)
            )
            
            if remaining_keys:
                # Find if this key matches any remaining keys
                similar_key = find_similar_keys_multilayer(entry.key, remaining_keys, user)
                
                if similar_key:
                    # Merge entries
                    try:
                        similar_entry = user_data_entries.get(key=similar_key)
                        
                        # Keep the newer entry
                        if entry.updated_at > similar_entry.updated_at:
                            similar_entry.delete()
                            logger.info(f"🔄 MERGED: Kept '{entry.key}', removed '{similar_key}'")
                        else:
                            entry.delete()
                            logger.info(f"🔄 MERGED: Kept '{similar_key}', removed '{entry.key}'")
                        
                        merged_count += 1
                        keys_processed.add(similar_key)
                        
                    except UserData.DoesNotExist:
                        pass
            
            keys_processed.add(entry.key)
        
        print(f"[DATA] Cleanup complete: {merged_count} duplicates merged")
        return merged_count
        
    except Exception as e:
        print(f"[ERROR] Error cleaning duplicate keys: {str(e)}")
        return 0

def handle_data_commands(user_message, user):
    """
    Handle special commands for data management
    Returns: (response_text, handled) tuple
    """
    message_lower = user_message.lower().strip()
    
    if message_lower in ['show my data', 'my data', 'what do you know about me']:
        user_data = get_user_data(user)
        if user_data:
            response = "Here's what I know about you:\n\n"
            for key, data in user_data.items():
                readable_key = key.replace('_', ' ').title()
                response += f"• {readable_key}: {data['value']}\n"
            return response, True
        else:
            return "I don't have any personal data stored about you yet. Share something about yourself!", True
    
    elif message_lower in ['clear my data', 'delete my data', 'forget about me']:
        deleted_count = UserData.objects.filter(user=user).count()
        UserData.objects.filter(user=user).delete()
        return f"I've cleared all your personal data ({deleted_count} items removed).", True
    
    elif message_lower in ['clean my data', 'fix my data', 'merge duplicates']:
        merged_count = cleanup_duplicate_keys(user)
        return f"I've cleaned up your data and merged {merged_count} duplicate entries.", True
    
    elif message_lower.startswith('update my ') or message_lower.startswith('change my '):
        return None, False
    
    return None, False