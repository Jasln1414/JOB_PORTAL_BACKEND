from rest_framework import serializers
from user_account.models import User,Education
from Empjob.models import Candidate, Employer, Jobs
from payment.models import Payment, EmployerSubscription, SubscriptionPlan
from Empjob.models import ApplyedJobs

# ------------------- User and Profile Serializers -------------------

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model, exposing basic user information.
    """
    class Meta:
        model = User
        fields = [
            'full_name', 'email', 'user_type', 'date_joined',
            'last_login', 'is_superuser', 'is_email_verified',
            'is_staff', 'is_active'
        ]

class EducationSerializer(serializers.ModelSerializer):
    """
    Serializer for Education model, detailing candidate education information.
    """
    class Meta:
        model = Education
        fields = ['education', 'college', 'specilization', 'completed', 'mark']

# ------------------- Candidate Serializers -------------------

class CandidateSerializer(serializers.ModelSerializer):
    """
    Serializer for Candidate model, providing a summary view with user details.
    """
    user_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = ['id', 'phone', 'profile_pic', 'user_name', 'email', 'status']

    def get_user_name(self, obj):
        return obj.user.full_name if obj.user.full_name else ""

    def get_email(self, obj):
        return obj.user.email if obj.user.email else ""

    def get_status(self, obj):
        return obj.user.is_active

class CandidateDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for Candidate model, including user and education details.
    """
    user = UserSerializer()
    education = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = [
            'id', 'phone', 'dob', 'profile_pic', 'Gender',
            'skills', 'resume', 'linkedin', 'github', 'place',
            'user', 'education'
        ]

    def get_education(self, obj):
        education = Education.objects.filter(user=obj.user)
        return EducationSerializer(education, many=True).data

# ------------------- Employer Serializers -------------------

class EmployerSerializer(serializers.ModelSerializer):
    """
    Serializer for Employer model, providing a summary view with user details.
    """
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    status = serializers.BooleanField(source='user.is_active', read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    is_approved_by_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = Employer
        fields = [
            'id', 'phone', 'profile_pic', 'user_name', 'email',
            'status', 'is_verified', 'is_approved_by_admin'
        ]

class AdminEmployerSerializer(serializers.ModelSerializer):
    """
    Serializer for Employer model tailored for admin use, with key details.
    """
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    status = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = Employer
        fields = [
            'id', 'user_name', 'email', 'status', 'profile_pic',
            'phone', 'is_verified', 'is_approved_by_admin'
        ]

class EmployerDetailsSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for Employer model, including user and associated jobs.
    """
    user = UserSerializer()
    jobs = serializers.SerializerMethodField()

    class Meta:
        model = Employer
        fields = '__all__'

    def get_jobs(self, obj):
        jobs = Jobs.objects.filter(employer=obj)
        return JobsSerializer(jobs, many=True).data

# ------------------- Job Serializers -------------------

class JobSerializer(serializers.ModelSerializer):
    """
    Serializer for Jobs model, providing a subset of job fields.
    """
    class Meta:
        model = Jobs
        fields = [
            'title', 'location', 'lpa', 'jobtype', 'jobmode',
            'experience', 'applyBefore', 'posteDate', 'about',
            'responsibility', 'active', 'employer', 'industry'
        ]

class JobsSerializer(serializers.ModelSerializer):
    """
    Serializer for Jobs model, exposing all fields.
    """
    class Meta:
        model = Jobs
        fields = '__all__'

class AdminJobSerializer(serializers.ModelSerializer):
    """
    Serializer for Jobs model tailored for admin use, including employer and application count.
    """
    employer = AdminEmployerSerializer(read_only=True)
    applications_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Jobs
        fields = '__all__'
        read_only_fields = ['posteDate', 'industry', 'employer']

    def get_applications_count(self, obj):
        try:
            return obj.applications.count()
        except AttributeError:
            return 0

    def update(self, instance, validated_data):
        """
        Custom update method to allow admins to modify specific fields.
        """
        if 'active' in validated_data:
            instance.active = validated_data.get('active')
        if 'moderation_note' in validated_data:
            instance.moderation_note = validated_data.get('moderation_note')
        instance.save()
        return instance

# ------------------- Subscription and Payment Serializers -------------------

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for SubscriptionPlan model, detailing plan attributes.
    """
    class Meta:
        model = SubscriptionPlan
        fields = ['name', 'description', 'price', 'job_limit', 'duration']

class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for Payment model, exposing all fields.
    """
    class Meta:
        model = Payment
        fields = '__all__'

class EmployerSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for EmployerSubscription model, including related employer, plan, and payment details.
    """
    employer = EmployerSerializer(read_only=True)
    plan = SubscriptionPlanSerializer(read_only=True)
    payment = PaymentSerializer(read_only=True)

    class Meta:
        model = EmployerSubscription
        fields = [
            'employer', 'plan', 'payment', 'status',
            'start_date', 'end_date', 'job_limit',
            'razorpay_subscription_id'
        ]



class ApplyedJobSerializer(serializers.ModelSerializer):
    """
    Serializer for ApplyedJobs model, including job details for applied jobs.
    """
    job = JobSerializer(read_only=True)

    class Meta:
        model = ApplyedJobs
        fields = ['id', 'job', 'status', 'applyed_on']

class JobSerializer(serializers.ModelSerializer):
    """
    Serializer for Jobs model, providing key job details.
    """
    class Meta:
        model = Jobs
        fields = ['title', 'location', 'lpa', 'experience']