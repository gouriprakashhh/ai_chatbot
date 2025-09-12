from functools import wraps
from django.shortcuts import redirect
from authentication.models import SessionStore

def session_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        session_id = request.session.get("session_id")

        if not session_id:
            return redirect("login")  # 🚨 No session → login

        try:
            session = SessionStore.objects.get(session_id=session_id)
        except SessionStore.DoesNotExist:
            return redirect("login")  # 🚨 Invalid session → login

        if not session.user or session.is_guest:
            return redirect("login")  # 🚨 Guest or no user → login

        # ✅ Attach session + user to request for easy use
        request.custom_session = session
        request.custom_user = session.user

        return view_func(request, *args, **kwargs)

    return _wrapped_view
