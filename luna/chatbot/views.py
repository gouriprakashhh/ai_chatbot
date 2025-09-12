import json
import logging
import os
import asyncio
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.views.decorators.http import require_POST
from asgiref.sync import sync_to_async, async_to_sync

from .decorators import session_login_required
from .models import ChatSession
from .utils import build_hybrid_memory, check_crisis, load_prompts, update_long_term_memory

logger = logging.getLogger(__name__)

# Ollama/Gemma API endpoint
GEMMA_API = getattr(settings, "GEMMA_API", "http://localhost:11434/api/generate")

@csrf_exempt
@session_login_required
def chat_view(request):
    """Render chat UI page"""
    return render(request, "chatbot/chat.html")

@csrf_exempt
@require_POST
@session_login_required

def ask_luna(request):
    """Handle user messages and stream Luna's response with user data extraction."""
    try:
        user_message = request.POST.get("message", "").strip()
        print(f"[DEBUG] Received message: {user_message}")
        if not user_message:
            print("[DEBUG] Empty message received")
            return JsonResponse({"error": "Message cannot be empty"}, status=400)

        user = request.custom_user
        session_id = request.session.session_key
        username = user.username
        print(f"[DEBUG] User: {username}, Session ID: {session_id}")

        # Ensure session exists
        chat_session, created = ChatSession.objects.get_or_create(
            user=user,
            session_id=session_id
        )
        print(f"[DEBUG] Chat session {'created' if created else 'retrieved'}: {chat_session}")

        # ------------------------
        # 1️⃣ Handle data management commands first
        # ------------------------
        from .utils import handle_data_commands
        data_response, data_handled = handle_data_commands(user_message, user)
        if data_handled:
            chat_session.add_message("user", user_message)
            chat_session.add_message("luna", data_response)
            print("[DEBUG] Handled data management command")
            return JsonResponse({
                "response": data_response,
                "action": None,
                "target": None,
                "delay": 5
            })

        # ------------------------
        # 2️⃣ Handle static commands
        # ------------------------
        from .utils import handle_user_command
        response_data, handled = handle_user_command(user_message, chat_session)
        print(f"[DEBUG] Static command handled: {handled}, response_data: {response_data}")
        if handled:
            chat_session.add_message("user", user_message)
            chat_session.add_message("luna", response_data["text"])
            print("[DEBUG] Saved static command messages to DB")
            return JsonResponse({
                "response": response_data["text"],
                "action": response_data.get("action"),
                "target": response_data.get("target"),
                "delay": response_data.get("delay", 5)
            })

        # ------------------------
        # 3️⃣ Extract user data if message contains personal information
        # ------------------------
        from .utils import should_extract_data, extract_user_data_with_ai
        print(f"[DEBUG] Checking if message contains user data...")
        should_extract = should_extract_data(user_message)
        print(f"[DEBUG] Should extract data: {should_extract}")
        
        if should_extract:
            print("[DEBUG] Message contains user data, starting extraction...")
            import threading
            
            def extract_data_background():
                try:
                    print("[DEBUG] Running background data extraction...")
                    extracted_data = extract_user_data_with_ai(user_message, user, chat_session)
                    if extracted_data:
                        print(f"[DEBUG] Successfully extracted user data: {list(extracted_data.keys())}")
                    else:
                        print("[DEBUG] No user data was extracted")
                except Exception as e:
                    print(f"[ERROR] Background data extraction failed: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            # Run data extraction in background to not slow down response
            thread = threading.Thread(target=extract_data_background)
            thread.daemon = True
            thread.start()
            print("[DEBUG] Started background data extraction thread")
        else:
            print("[DEBUG] Message does not contain extractable user data")

        # ------------------------
        # 4️⃣ Save user message
        # ------------------------
        chat_session.add_message("user", user_message)
        print("[DEBUG] Saved user message to DB")

        # ------------------------
        # 5️⃣ Check for crisis content
        # ------------------------
        is_crisis, crisis_score, triggered_keywords = check_crisis(user_message)
        print(f"[DEBUG] Crisis check: {is_crisis}, score: {crisis_score}, keywords: {triggered_keywords}")
        if is_crisis:
            print(f"[WARNING] Crisis detected for user {username}")

        # ------------------------
        # 6️⃣ Build memory prompt with user context
        # ------------------------
        conversation = build_hybrid_memory(chat_session, user_message, limit=5)
        
        # Add user personal data context
        from .utils import build_user_context
        user_context = build_user_context(user)
        if user_context:
            print("[DEBUG] Added user personal data context to prompt")
        
        prompt = load_prompts(username, conversation, user_context)
        print(f"[DEBUG] Built prompt for Gemma: {prompt[:200]}...")  # first 200 chars

        payload = {
            "model": "gemma3:12b",
            "prompt": prompt,
            "stream": True,
            "max_tokens": 250,
            "temperature": 0.7,
            "top_p": 0.9,
        }

        # ------------------------
        # 7️⃣ Stream response
        # ------------------------
        def stream_response():
            luna_response = []
            crisis_handled = is_crisis

            try:
                import requests
                print(f"[DEBUG] Sending request to GEMMA_API: {GEMMA_API}")
                response = requests.post(GEMMA_API, json=payload, stream=True, timeout=90)
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                        if "response" in data:
                            chunk = data["response"]
                            luna_response.append(chunk)
                            print(f"[DEBUG] Streaming chunk: {chunk[:50]}...")  # first 50 chars
                            yield chunk
                    except json.JSONDecodeError as jde:
                        print(f"[ERROR] JSON decode error in stream line: {jde}")
                        continue

            except Exception as e:
                error_msg = "[Sorry, I'm having trouble responding right now. Please try again.]"
                print(f"[ERROR] Error contacting Gemma API: {str(e)}")
                yield error_msg
                luna_response.append(error_msg)

            # ------------------------
            # 8️⃣ Process full response
            # ------------------------
            full_response = "".join(luna_response).strip()
            print(f"[DEBUG] Full streamed response: {full_response[:200]}...")

            if not crisis_handled:
                luna_is_crisis, luna_crisis_score, luna_triggered = check_crisis(full_response)
                crisis_handled = luna_is_crisis
                print(f"[DEBUG] Post-response crisis check: {crisis_handled}, score: {luna_crisis_score}")

            if crisis_handled:
                try:
                    crisis_file = os.path.join(settings.BASE_DIR, "prompts", "safety.txt")
                    with open(crisis_file, "r", encoding="utf-8") as f:
                        crisis_text = f.read().strip()
                    if crisis_text not in full_response:
                        full_response = f"{full_response}\n\n{crisis_text}"
                    print("[DEBUG] Appended crisis resources to response")
                except Exception as e:
                    print(f"[ERROR] Failed to load crisis file: {str(e)}")
                    full_response += "\n\nIf you're in crisis, please reach out to a mental health professional or crisis helpline."

            # ------------------------
            # 9️⃣ Parse Gemma command
            # ------------------------
            from .utils import parse_gemma_response, VALID_URLS
            parsed = parse_gemma_response(full_response)
            target = parsed.get("target")
            if target and target not in VALID_URLS:
                print(f"[WARNING] Invalid redirect target from Gemma: {target}")
                parsed["action"] = None
                parsed["target"] = None
                parsed["text"] += "\n(Note: I couldn't find that page. Please try again.)"

            # ------------------------
            # 10️⃣ Save response
            # ------------------------
            chat_session.add_message("luna", parsed.get("text", full_response))
            print("[DEBUG] Saved Luna response to DB")

            # ------------------------
            # 11️⃣ Update memory in background
            # ------------------------
            import threading
            def update_memory_background():
                try:
                    update_long_term_memory(chat_session)
                    print("[DEBUG] Long-term memory updated successfully")
                except Exception as e:
                    print(f"[ERROR] Memory update failed: {str(e)}")
            thread = threading.Thread(target=update_memory_background)
            thread.daemon = True
            thread.start()

            # ------------------------
            # 12️⃣ Yield command JSON after streaming
            # ------------------------
            if parsed.get("action") or parsed.get("target"):
                command_json = {
                    "action": parsed.get("action"),
                    "target": parsed.get("target"),
                    "delay": parsed.get("delay", 5)
                }
                print(f"[DEBUG] Yielding command JSON: {command_json}")
                yield f"\n__COMMAND__START__\n{json.dumps(command_json)}\n__COMMAND__END__\n"

        return StreamingHttpResponse(stream_response(), content_type="text/plain")

    except Exception as e:
        print(f"[ERROR] Unexpected error in ask_luna: {str(e)}", flush=True)
        return JsonResponse({"error": "An unexpected error occurred. Please try again."}, status=500)


# Health check endpoint
@csrf_exempt
def health_check(request):
    """Simple health check endpoint"""
    return JsonResponse({"status": "ok", "service": "Luna Chat API"})

# Get conversation history
@csrf_exempt
@require_POST
@session_login_required
def get_conversation_history(request):
    """Get conversation history for the current session"""
    try:
        user = request.custom_user
        session_id = request.session.session_key
        
        chat_session = ChatSession.objects.get(
            user=user, session_id=session_id
        )
        
        return JsonResponse({
            "conversation": chat_session.conversation or [],
            "memory": chat_session.memory or ""
        })
    except ChatSession.DoesNotExist:
        return JsonResponse({"conversation": [], "memory": ""})
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        return JsonResponse({"error": "Failed to retrieve conversation history"}, status=500)

# Clear conversation
@csrf_exempt
@require_POST
@session_login_required
def clear_conversation(request):
    """Clear the current conversation"""
    try:
        user = request.custom_user
        session_id = request.session.session_key
        
        chat_session = ChatSession.objects.get(
            user=user, session_id=session_id
        )
        
        chat_session.conversation = []
        chat_session.memory = ""
        chat_session.save(update_fields=["conversation", "memory"])
        
        return JsonResponse({"status": "conversation cleared"})
    except Exception as e:
        logger.error(f"Error clearing conversation: {str(e)}")
        return JsonResponse({"error": "Failed to clear conversation"}, status=500)