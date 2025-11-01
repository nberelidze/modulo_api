from django.contrib import admin
from .models import PatientToken


@admin.register(PatientToken)
class PatientTokenAdmin(admin.ModelAdmin):
    list_display = ('personal_number', 'token_type', 'session_id', 'is_revoked', 'expires_at', 'created_at')
    list_filter = ('token_type', 'is_revoked', 'expires_at', 'created_at')
    search_fields = ('personal_number', 'jti', 'mobile_phone')
    readonly_fields = ('jti', 'created_at', 'last_used_at', 'revoked_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Token Info', {
            'fields': ('jti', 'token_type', 'expires_at')
        }),
        ('Patient Info', {
            'fields': ('personal_number', 'mobile_phone')
        }),
        ('Session', {
            'fields': ('session_id', 'device_name')
        }),
        ('Status', {
            'fields': ('is_revoked', 'revoked_at', 'revocation_reason', 'last_used_at')
        }),
        ('Audit', {
            'fields': ('client_ip', 'user_agent', 'created_at'),
            'classes': ('collapse',)
        }),
    )
