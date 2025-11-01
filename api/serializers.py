from rest_framework import serializers

from zoneinfo import ZoneInfo

tzTBS = ZoneInfo('Asia/Tbilisi')

class ExaminationResultSerializer(serializers.Serializer):
    #researchKod = serializers.CharField()
    #researchCode = serializers.CharField()
    AnalyzeCode = serializers.CharField()
    Id = serializers.CharField()
    Name = serializers.CharField()
    Normative = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    NormativeMin = serializers.DecimalField(required=False, allow_null=True, max_digits=None, decimal_places=3)
    NormativeMax = serializers.DecimalField(required=False, allow_null=True, max_digits=None, decimal_places=3)
    Unit = serializers.CharField()
    Result = serializers.CharField()
    TextResult = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Comment = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    CompleteDatetime = serializers.DateTimeField(required=False, allow_null=True)
    CompletedBy = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    VerifyDatetime = serializers.DateTimeField(required=False, allow_null=True)
    VerifiedBy = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Instrument = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    #Instrument2 = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    IsCalculated = serializers.BooleanField(required=False, default=False)
    State = serializers.CharField()

class ExaminationResultsSerializer(serializers.Serializer):
    results = serializers.ListField(child=ExaminationResultSerializer())

class ExaminationResultSerializerDoctra(serializers.Serializer):
    AnalyzeCode = serializers.CharField()
    AnalyzeCodeExt = serializers.CharField(default='', allow_null=True)
    Id = serializers.CharField()
    Name = serializers.CharField()
    Normative = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    NormativeMin = serializers.DecimalField(required=False, allow_null=True, max_digits=None, decimal_places=3)
    NormativeMax = serializers.DecimalField(required=False, allow_null=True, max_digits=None, decimal_places=3)
    Unit = serializers.CharField()
    Result = serializers.CharField()
    TextResult = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Comment = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    CompleteDatetime = serializers.DateTimeField(required=False, allow_null=True)
    ResponsiblePerson = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    # VerifyDatetime = serializers.DateTimeField(required=False, allow_null=True)
    # VerifiedBy = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Instrument = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    #Instrument2 = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    IsCalculated = serializers.BooleanField(required=False, default=False)
    State = serializers.CharField()

class ExaminationResultsSerializerDoctra(serializers.Serializer):
    results = serializers.ListField(child=ExaminationResultSerializerDoctra())

#Single results
class ExaminationResultPDFSerializer(serializers.Serializer):
    Name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    ErrorCode = serializers.IntegerField()
    ErrorMessage = serializers.CharField(required=False, allow_null=True, allow_blank=True)

#Multiple results
class ExaminationResultsPDFSerializer(serializers.Serializer):
    results = serializers.ListField(child=ExaminationResultPDFSerializer())

class LabTestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    lis_code = serializers.CharField(allow_null=True)
    ss_code = serializers.CharField(allow_null=True)
    name = serializers.CharField(allow_null=True)
    active = serializers.BooleanField()
    list_price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    web_category_id = serializers.IntegerField(allow_null=True)

class LabTestsSerializer(serializers.Serializer):
    results = serializers.ListField(child=LabTestSerializer())

class LabTestCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True)
    country_id = serializers.IntegerField(allow_null=True)
    country_name = serializers.CharField(allow_null=True)

class LabTestCategoriesSerializer(serializers.Serializer):
    results = serializers.ListField(child=LabTestCategorySerializer())

class LabTestParameterSerializer(serializers.Serializer):
    code = serializers.CharField(allow_null=True)
    name = serializers.CharField(allow_null=True)

class LabTestParametersSerializer(serializers.Serializer):
    results = serializers.ListField(child=LabTestParameterSerializer())

#RAW Result from inno_results
class ExaminationResultRawSerializer(serializers.Serializer):
    RecordID = serializers.IntegerField()
    Hardware_SN = serializers.CharField()
    Barcode = serializers.CharField()
    Parametter = serializers.CharField()
    UOM = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Result = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    CompletedDatetime = serializers.DateTimeField(default_timezone=tzTBS)

class ExaminationResultsRawSerializer(serializers.Serializer):
    results = serializers.ListField(child=ExaminationResultRawSerializer())

class GetPatientRequestSerializer(serializers.Serializer):
    personalNumber = serializers.CharField()

    def validate_personalNumber(self, value):
        """
        Sanitize and validate the personal number to ensure it contains exactly 11 digits.
        """
        # Remove any non-digit characters
        sanitized = ''.join(filter(str.isdigit, str(value)))
        
        if not sanitized:
            raise serializers.ValidationError("Personal number must contain at least one digit.")
        
        if len(sanitized) != 11:
            raise serializers.ValidationError(f"Personal number must be exactly 11 digits. Received {len(sanitized)} digits.")
        
        return sanitized

class GetPatientResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField(required=False, allow_null=True)
    last_name = serializers.CharField(required=False, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_null=True)
    mobile_phone = serializers.CharField(required=False, allow_null=True)
    email = serializers.CharField(required=False, allow_null=True)
    inno_code = serializers.CharField(required=False, allow_null=True)

class GetPatientResponseListSerializer(serializers.Serializer):
    patients = GetPatientResponseSerializer(many=True)

class CheckPatientExistsRequestSerializer(serializers.Serializer):
    personalNumber = serializers.CharField()
    mobilePhone = serializers.CharField()

    def validate_personalNumber(self, value):
        """
        Sanitize and validate the personal number to ensure it contains exactly 11 digits.
        """
        # Remove any non-digit characters
        sanitized = ''.join(filter(str.isdigit, str(value)))
        
        if not sanitized:
            raise serializers.ValidationError("Personal number must contain at least one digit.")
        
        if len(sanitized) != 11:
            raise serializers.ValidationError(f"Personal number must be exactly 11 digits. Received {len(sanitized)} digits.")
        
        return sanitized

    def validate_mobilePhone(self, value):
        """
        Sanitize and validate mobile phone.
        Georgian mobile format: 5 followed by 8 digits (e.g., 555123456).
        """
        if not value:
            raise serializers.ValidationError("Mobile phone is required.")
        
        # Remove non-digit characters
        sanitized = ''.join(filter(str.isdigit, str(value)))
        
        # Remove leading country code if present (995 for Georgia)
        if sanitized.startswith('995') and len(sanitized) == 12:
            sanitized = sanitized[3:]
        
        if not sanitized:
            raise serializers.ValidationError("Mobile phone must contain at least one digit.")
        
        # Validate Georgian mobile format: 5 followed by 8 digits
        if len(sanitized) != 9:
            raise serializers.ValidationError(f"Mobile phone must be 9 digits (5 + 8). Received {len(sanitized)} digits.")
        
        if not sanitized.startswith('5'):
            raise serializers.ValidationError("Mobile phone must start with 5.")
        
        return sanitized

class CheckPatientExistsResponseSerializer(serializers.Serializer):
    exists = serializers.BooleanField()
    accessToken = serializers.CharField(required=False, help_text="JWT access token (returned only when exists=True)")
    refreshToken = serializers.CharField(required=False, help_text="JWT refresh token (returned only when exists=True)")
    expiresIn = serializers.IntegerField(required=False, help_text="Access token lifetime in seconds (returned only when exists=True)")


class TokenRefreshRequestSerializer(serializers.Serializer):
    refreshToken = serializers.CharField(required=True, help_text="The refresh token to use for getting a new access token")


class TokenRefreshResponseSerializer(serializers.Serializer):
    accessToken = serializers.CharField(help_text="New JWT access token")
    refreshToken = serializers.CharField(required=False, help_text="New refresh token (if rotation is enabled)")
    expiresIn = serializers.IntegerField(help_text="Access token lifetime in seconds")


class RevokeTokenRequestSerializer(serializers.Serializer):
    personalNumber = serializers.CharField(max_length=11, required=True, help_text="Patient personal identification number")
    reason = serializers.CharField(max_length=255, required=False, help_text="Reason for token revocation")


class RevokeTokenResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    tokensRevoked = serializers.IntegerField(help_text="Number of tokens revoked")
    message = serializers.CharField()


class PatientSessionSerializer(serializers.Serializer):
    sessionId = serializers.UUIDField(help_text="Unique session identifier")
    deviceName = serializers.CharField(help_text="Device/browser that created this session")
    createdAt = serializers.DateTimeField(help_text="When the session was created")
    lastUsedAt = serializers.DateTimeField(help_text="When the session was last used")
    clientIp = serializers.CharField(help_text="IP address of the device")
    isActive = serializers.BooleanField(help_text="Whether the session has active (non-revoked, non-expired) tokens")


class GetSessionsResponseSerializer(serializers.Serializer):
    sessions = PatientSessionSerializer(many=True, help_text="List of active sessions for the patient")
    totalSessions = serializers.IntegerField(help_text="Total number of sessions")


class RevokeSessionRequestSerializer(serializers.Serializer):
    sessionId = serializers.UUIDField(required=True, help_text="Session ID to revoke")


class RevokeSessionResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    tokensRevoked = serializers.IntegerField(help_text="Number of tokens revoked in this session")
    message = serializers.CharField()
