from django.db import models
from django.db.models import Max, Min, Count

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Create your models here.

class PatientToken(models.Model):
    """
    Model for tracking JWT tokens issued to patients.
    Provides audit trail, session management, and revocation capability.
    """
    jti = models.CharField(max_length=255, unique=True, db_index=True, help_text=_(
        'JWT Token ID (jti claim) - unique identifier for the token'
    ))
    personal_number = models.CharField(max_length=11, db_index=True, help_text=_(
        'Patient personal identification number (11 digits)'
    ))
    mobile_phone = models.CharField(max_length=9, help_text=_(
        'Patient mobile phone number (9 digits, without country code)'
    ))
    token_type = models.CharField(max_length=10, choices=[
        ('access', _('Access Token')),
        ('refresh', _('Refresh Token'))
    ], help_text=_('Type of token'))
    
    # Session Management
    session_id = models.UUIDField(null=True, blank=True, db_index=True, help_text=_(
        'Session identifier - groups access and refresh tokens together'
    ))
    device_name = models.CharField(max_length=200, blank=True, null=True, help_text=_(
        'Device/browser name (e.g., "Chrome on Windows", "Safari on iPhone")'
    ))
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, help_text=_(
        'When the token was issued'
    ))
    expires_at = models.DateTimeField(help_text=_(
        'When the token expires'
    ))
    last_used_at = models.DateTimeField(null=True, blank=True, help_text=_(
        'Last time this token was used for authentication'
    ))
    
    # Revocation
    is_revoked = models.BooleanField(default=False, db_index=True, help_text=_(
        'Whether this token has been revoked'
    ))
    revoked_at = models.DateTimeField(null=True, blank=True, help_text=_(
        'When the token was revoked'
    ))
    revocation_reason = models.CharField(max_length=255, blank=True, null=True, help_text=_(
        'Reason for token revocation'
    ))
    
    # Audit fields
    client_ip = models.GenericIPAddressField(null=True, blank=True, help_text=_(
        'IP address from which the token was requested'
    ))
    user_agent = models.TextField(blank=True, null=True, help_text=_(
        'User agent string from token request'
    ))
    
    class Meta:
        db_table = 'patient_tokens'
        verbose_name = _('Patient Token')
        verbose_name_plural = _('Patient Tokens')
        indexes = [
            models.Index(fields=['personal_number', 'is_revoked']),
            models.Index(fields=['expires_at', 'is_revoked']),
            models.Index(fields=['session_id', 'is_revoked']),
            models.Index(fields=['personal_number', 'session_id', 'is_revoked']),
        ]
    
    def __str__(self):
        return f"{self.token_type} token for {self.personal_number} (jti: {self.jti[:8]}...)"
    
    def revoke(self, reason=None):
        """Revoke this token."""
        self.is_revoked = True
        self.revoked_at = timezone.now()
        if reason:
            self.revocation_reason = reason
        self.save(update_fields=['is_revoked', 'revoked_at', 'revocation_reason'])
    
    def is_valid(self):
        """Check if token is still valid (not expired and not revoked)."""
        return not self.is_revoked and self.expires_at > timezone.now()
    
    @classmethod
    def revoke_all_for_patient(cls, personal_number, reason=None):
        """Revoke all tokens for a specific patient."""
        tokens = cls.objects.filter(
            personal_number=personal_number,
            is_revoked=False
        )
        now = timezone.now()
        tokens.update(
            is_revoked=True,
            revoked_at=now,
            revocation_reason=reason or 'Bulk revocation'
        )
        return tokens.count()
    
    @classmethod
    def revoke_session(cls, personal_number, session_id, reason=None):
        """Revoke all tokens for a specific session belonging to a patient."""
        tokens = cls.objects.filter(
            personal_number=personal_number,
            session_id=session_id,
            is_revoked=False
        )
        now = timezone.now()
        tokens.update(
            is_revoked=True,
            revoked_at=now,
            revocation_reason=reason or 'Session revoked'
        )
        return tokens.count()
    
    @classmethod
    def get_active_sessions(cls, personal_number):
        """
        Get all active sessions for a patient.
        Returns list of session info with latest activity.
        """
        sessions = cls.objects.filter(
            personal_number=personal_number,
            session_id__isnull=False,  # Only sessions with session_id
            is_revoked=False,
            expires_at__gt=timezone.now()
        ).values('session_id').annotate(
            created_at=Min('created_at'),
            last_used_at=Max('last_used_at'),
            device_name=Max('device_name'),
            client_ip=Max('client_ip'),
            token_count=Count('id')
        ).order_by('-last_used_at')
        
        return list(sessions)
