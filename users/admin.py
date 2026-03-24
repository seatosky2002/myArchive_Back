from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'nickname', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('email', 'nickname')
    ordering = ('-date_joined',)
    fieldsets = UserAdmin.fieldsets + (
        ('추가 정보', {'fields': ('nickname', 'profile_img_url')}),
    )
