import functools

from rest_framework import serializers

from zoneinfo import ZoneInfo

tzTBS = ZoneInfo('Asia/Tbilisi')

class OerpSerializerMixin:
    """
    Converts OpenERP's False-for-null convention to None before validation.
    OpenERP v7 returns boolean False for any unset field over XML-RPC.
    """
    @functools.cached_property
    def _non_nullable_bool_fields(self):
        return {
            name
            for name, field in self.fields.items()
            if isinstance(field, serializers.BooleanField) and not field.allow_null
        }

    def _fix_oerp_false(self, data):
        """Convert OpenERP's False-for-null to None, preserving actual boolean False."""
        return {
            k: (v if k in self._non_nullable_bool_fields else (None if v is False else v))
            for k, v in data.items()
        }

    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = self._fix_oerp_false(data)
        return super().to_internal_value(data)

    def to_representation(self, instance):
        if isinstance(instance, dict):
            instance = self._fix_oerp_false(instance)
        return super().to_representation(instance)

class ExaminationResultSerializer(OerpSerializerMixin, serializers.Serializer):
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

class ExaminationResultSerializerDoctra(OerpSerializerMixin, serializers.Serializer):
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
class ExaminationResultPDFSerializer(OerpSerializerMixin, serializers.Serializer):
    Name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    Url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    ErrorCode = serializers.IntegerField()
    ErrorMessage = serializers.CharField(required=False, allow_null=True, allow_blank=True)

#Multiple results
class ExaminationResultsPDFSerializer(serializers.Serializer):
    results = serializers.ListField(child=ExaminationResultPDFSerializer())

class LabSubtestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True)
    name_geo = serializers.CharField(allow_null=True)
    sequence = serializers.IntegerField()

class LabTestSerializer(OerpSerializerMixin, serializers.Serializer):
    id = serializers.IntegerField()
    lis_code = serializers.CharField(allow_null=True)
    ss_code = serializers.CharField(allow_null=True)
    name = serializers.CharField(allow_null=True)
    name_geo = serializers.CharField(allow_null=True)
    active = serializers.BooleanField()
    list_price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    web_category_id = serializers.IntegerField(allow_null=True)
    preparation_notes = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    preparation_notes_geo = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    country_id = serializers.IntegerField(allow_null=True)
    country_name = serializers.CharField(allow_null=True)
    country_name_geo = serializers.CharField(allow_null=True)
    subtests = LabSubtestSerializer(many=True, required=False, default=list)
    has_pdf = serializers.BooleanField(default=False)
    seo_keywords = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    web_notes = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    web_notes_geo = serializers.CharField(allow_null=True, required=False, allow_blank=True)

class LabTestsSerializer(serializers.Serializer):
    results = serializers.ListField(child=LabTestSerializer())

class LabTestCategorySerializer(OerpSerializerMixin, serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True)
    name_geo = serializers.CharField(allow_null=True)
    country_id = serializers.IntegerField(allow_null=True)
    country_name = serializers.CharField(allow_null=True)
    country_name_geo = serializers.CharField(allow_null=True)

class LabTestCategoriesSerializer(serializers.Serializer):
    results = serializers.ListField(child=LabTestCategorySerializer())

class LabTestParameterSerializer(OerpSerializerMixin, serializers.Serializer):
    code = serializers.CharField(allow_null=True)
    name = serializers.CharField(allow_null=True)
    name_geo = serializers.CharField(allow_null=True)

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

class LabOrderParameterSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    parameter_id = serializers.IntegerField()
    parameter_name = serializers.CharField(allow_null=True, required=False)
    parameter_name_geo = serializers.CharField(allow_null=True, required=False)
    parameter_abbr = serializers.CharField(allow_null=True, required=False)
    # research_id = serializers.IntegerField()
    # research_name = serializers.CharField(allow_null=True, required=False)
    value = serializers.DecimalField(max_digits=None, decimal_places=10, allow_null=True, required=False, normalize_output=True)
    value_min = serializers.DecimalField(max_digits=None, decimal_places=10, allow_null=True, required=False, normalize_output=True)
    value_max = serializers.DecimalField(max_digits=None, decimal_places=10, allow_null=True, required=False, normalize_output=True)
    reference_range = serializers.CharField(allow_null=True, required=False)
    uom_name = serializers.CharField(allow_null=True, required=False)
    value_text = serializers.CharField(allow_null=True, required=False)
    value_text_geo = serializers.CharField(allow_null=True, required=False)
    value_text_ref = serializers.CharField(allow_null=True, required=False)
    value_text_ref_geo = serializers.CharField(allow_null=True, required=False)
    abnormal_indicator = serializers.CharField(allow_null=True, required=False)
    # value_auto = serializers.DecimalField(max_digits=None, decimal_places=10, allow_null=True, required=False)
    # value_1 = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    # value_2 = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    # value_3 = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    # text_value = serializers.IntegerField(allow_null=True, required=False)
    # value_text_auto = serializers.IntegerField(allow_null=True, required=False)
    uom_id = serializers.IntegerField()
    uom_name = serializers.CharField(allow_null=True, required=False)
    state = serializers.CharField(allow_null=True, required=False)
    comment = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    commenten = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    # date_value = serializers.DateTimeField(allow_null=True, required=False)
    sequence = serializers.IntegerField(allow_null=True, required=False)
    # is_printable = serializers.BooleanField(allow_null=True, required=False)
    # do_not_print = serializers.BooleanField(allow_null=True, required=False)
    # instrument_id = serializers.IntegerField(allow_null=True, required=False)
    instrument_name = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    # default_instrument_code = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    updated_at = serializers.DateTimeField(allow_null=True, required=False)
    # updated_by = serializers.IntegerField(allow_null=True, required=False)
    reference_range = serializers.CharField(allow_null=True, required=False)

class LabOrderPDFSerializer(serializers.Serializer):
    uuid = serializers.CharField(allow_null=True)
    name = serializers.CharField(allow_null=True, required=False)
    comment = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    url = serializers.CharField(help_text="Full URL to the PDF file")

class LabOrderDetailSerializer(serializers.Serializer):
    """Serializer for lab order. Can include optional parameters field."""
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=64)
    state = serializers.CharField(allow_null=True, required=False)
    # shop_id = serializers.IntegerField()
    date_order = serializers.DateTimeField(allow_null=True, required=False)
    # partner_id = serializers.IntegerField()
    # add_id = serializers.IntegerField(allow_null=True, required=False)
    # inno_height = serializers.FloatField(allow_null=True, required=False)
    # inno_weight = serializers.FloatField(allow_null=True, required=False)
    categ_id = serializers.IntegerField()
    user_portal_categ_id = serializers.IntegerField(allow_null=True, required=False)
    user_portal_categ_name = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    user_portal_categ_name_geo = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    date_done = serializers.DateTimeField(allow_null=True, required=False)
    # print_urin = serializers.BooleanField(allow_null=True, required=False)
    # active = serializers.BooleanField(allow_null=True, required=False)
    comment_inside = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    comment_inside_en = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    # cap_blood = serializers.BooleanField(allow_null=True, required=False)
    # erythrocyte = serializers.BooleanField(allow_null=True, required=False)
    # not_read = serializers.BooleanField(allow_null=True, required=False)
    create_date = serializers.DateTimeField(allow_null=True, required=False)
    write_date = serializers.DateTimeField(allow_null=True, required=False)
    parameters = LabOrderParameterSerializer(many=True, required=False, help_text="List of test parameters for this lab order")
    pdf_files = LabOrderPDFSerializer(many=True, required=False, default=list, help_text="List of PDF files associated with this lab order")
    has_details = serializers.BooleanField(required=False, default=False, help_text="Indicates if the lab order has detailed parameters available")

class LabOrdersSerializer(serializers.Serializer):
    labOrders = LabOrderDetailSerializer(many=True, help_text="List of lab orders for the patient")
    totalLabOrders = serializers.IntegerField(help_text="Total number of lab orders")


class LabOrderStatSerializer(serializers.Serializer):
    laborder_id = serializers.IntegerField(help_text="Lab order ID")
    categ_id = serializers.IntegerField(help_text="Category ID")
    categ_name_eng = serializers.CharField(help_text="Category name ENG", allow_null=True)
    categ_name_geo = serializers.CharField(help_text="Category name GEO", allow_null=True)
    date = serializers.DateField(allow_null=True, required=False, help_text="Date of the test value")
    param_id_uom = serializers.CharField(help_text="Parameter ID and UOM ID concatenated")
    parameter = serializers.CharField(help_text="Parameter name (localized if available)")
    value = serializers.CharField(allow_null=True, required=False, allow_blank=True, help_text="Test result value")
    orderby = serializers.IntegerField(allow_null=True, required=False, help_text="Sequence order")


class LabOrderStatsSerializer(serializers.Serializer):
    stats = LabOrderStatSerializer(many=True, help_text="Lab order statistics for the patient")
    totalRecords = serializers.IntegerField(help_text="Total number of records")


class PatientDataSerializer(serializers.Serializer):
    """Base serializer for patient data. Used in both patient creation and order creation."""
    externalCode = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="External system code/reference")
    personalNumber = serializers.CharField(help_text="11-digit Georgian personal identification number")
    name = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Full name (optional, will be generated from first/last name if not provided)")
    firstName = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Patient's first name")
    lastName = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Patient's last name")
    dateOfBirth = serializers.DateField(required=False, allow_null=True, help_text="Date of birth (YYYY-MM-DD)")
    sex = serializers.ChoiceField(choices=['male', 'female'], required=False, allow_null=True, help_text="Gender: 'male' or 'female'")
    note = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Additional notes")

    def validate_personalNumber(self, value):
        """Validate personal number is exactly 11 digits."""
        sanitized = ''.join(filter(str.isdigit, str(value)))
        if len(sanitized) != 11:
            raise serializers.ValidationError(f"Personal number must be exactly 11 digits. Received {len(sanitized)} digits.")
        return sanitized


class CreatePatientRequestSerializer(PatientDataSerializer):
    """Serializer for creating a new patient. Makes required fields explicit."""
    firstName = serializers.CharField(help_text="Patient's first name")
    lastName = serializers.CharField(help_text="Patient's last name")
    dateOfBirth = serializers.DateField(help_text="Date of birth (YYYY-MM-DD)")
    sex = serializers.ChoiceField(choices=['male', 'female'], help_text="Gender: 'male' or 'female'")


class CreatePatientResponseSerializer(serializers.Serializer):
    partnerId = serializers.IntegerField(help_text="OpenERP partner ID")
    patientCode = serializers.CharField(help_text="Generated patient code (e.g., 'XY12345' or 'XX67890')")
    personalNumber = serializers.CharField(help_text="Patient's personal identification number")
    firstName = serializers.CharField(help_text="Patient's first name")
    lastName = serializers.CharField(help_text="Patient's last name")
    name = serializers.CharField(help_text="Full name")
    dateOfBirth = serializers.DateField(help_text="Date of birth")
    sex = serializers.CharField(help_text="Gender")
    externalCode = serializers.CharField(required=False, allow_null=True, help_text="External system code/reference")
    note = serializers.CharField(required=False, allow_null=True, help_text="Additional notes")


class OrderTestSerializer(serializers.Serializer):
    testCode = serializers.CharField(help_text="Test code matching product.product.default_code")
    transactionCode = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Transaction code for tracking")


class OrderExternalInfoSerializer(serializers.Serializer):
    visitNumber = serializers.CharField(help_text="Visit number for the order")


class CreateOrderRequestSerializer(serializers.Serializer):
    datetime = serializers.DateTimeField(help_text="Order date and time")
    externalInfo = OrderExternalInfoSerializer(help_text="External information including visit number")
    patient = PatientDataSerializer(help_text="Patient information")
    weight = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Patient weight")
    height = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Patient height")
    volume = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Sample volume")
    pregnancyWeek = serializers.IntegerField(required=False, allow_null=True, help_text="Pregnancy week")
    urgent = serializers.BooleanField(default=False, help_text="Whether the order is urgent")
    tests = OrderTestSerializer(many=True, help_text="List of tests to order")


class CreateOrderResponseSerializer(serializers.Serializer):
    orderId = serializers.IntegerField(help_text="OpenERP sale order ID")
    orderName = serializers.CharField(help_text="Sale order number/name")
    partnerId = serializers.IntegerField(help_text="Partner ID")
    patientCode = serializers.CharField(required=False, allow_null=True, help_text="Patient code")
    visitNumber = serializers.CharField(help_text="Visit number")
    testCount = serializers.IntegerField(help_text="Number of tests in the order")
    orderLines = serializers.ListField(child=serializers.IntegerField(), help_text="List of created order line IDs")


class PivotTableRequestSerializer(serializers.Serializer):
    categoryId = serializers.IntegerField(help_text="Lab test category ID to filter results")
    maxResults = serializers.IntegerField(
        required=False, 
        default=5, 
        min_value=1,
        max_value=50,
        help_text="Maximum number of most recent test results to include (default: 5, max: 50)"
    )


class PivotTableResponseSerializer(serializers.Serializer):
    categoryId = serializers.IntegerField(help_text="Lab test category ID")
    categoryName = serializers.CharField(help_text="Category name")
    patientId = serializers.IntegerField(help_text="Patient partner ID")
    columns = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of column definitions with laborder_id and date"
    )
    rows = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of parameter rows with values for each date"
    )
    totalRows = serializers.IntegerField(help_text="Total number of parameter rows")


class LabTestPDFsSerializer(serializers.Serializer):
    pdf_eng = serializers.CharField(allow_null=True, help_text="Base64-encoded English PDF")
    pdf_eng_filename = serializers.CharField(allow_null=True, help_text="English PDF filename")
    pdf_geo = serializers.CharField(allow_null=True, help_text="Base64-encoded Georgian PDF")
    pdf_geo_filename = serializers.CharField(allow_null=True, help_text="Georgian PDF filename")

