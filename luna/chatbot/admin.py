from django.contrib import admin
from .models import ChatSession,UserData
# Register your models here.


admin.site.register(ChatSession)
# admin.py
# admin.py
from django.contrib import admin
from authentication.models import UserAccount
from .models import UserData

class UserDataInline(admin.TabularInline):
    model = UserData
    extra = 0  # no empty rows
    fields = ('key', 'value', 'data_type', 'confidence_score')
    show_change_link = True  # link to open UserData separately
    can_delete = True        # ✅ allows delete checkbox

@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    list_display = ('username', 'email')
    search_fields = ('username', 'email')
    inlines = [UserDataInline]

@admin.register(UserData)
class UserDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'value')
    search_fields = ('user__username', 'key', 'value')
