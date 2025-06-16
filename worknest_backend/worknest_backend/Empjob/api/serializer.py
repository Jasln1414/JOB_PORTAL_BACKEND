"""Module containing serializers for the job application and user management API.

This module provides serializers for handling data serialization and
deserialization for models related to jobs, employers, candidates, and
applications using Django REST Framework.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging
import os

from Empjob.models import Jobs, Question, Answer, ApplyedJobs, SavedJobs, Approvals
from user_account.models import Employer, Candidate, Education

# Configure logging
logger = logging.getLogger(__name__)

User = get_user_model()


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer for Question model.

    Serializes question data including ID, text, and question type.
    """

    class Meta:
        model = Question
        fields = ['id', 'text']


class PostJobSerializer(serializers.ModelSerializer):
    """Serializer for creating job postings with associated questions.

    Allows creation of a job with optional questions, linked to an employer.
    """

    questions = QuestionSerializer(many=True, required=False)

    class Meta:
        model = Jobs
        fields = '__all__'
        depth = 1

    def create(self, validated_data):
        """Create a new job and its associated questions.

        Args:
            validated_data (dict): Validated data for job creation.

        Returns:
            Jobs: Created job instance.
        """
        questions_data = validated_data.pop('questions', [])
        employer = self.context['employer']
        job = Jobs.objects.create(employer=employer, **validated_data)

        for question_data in questions_data:
            Question.objects.create(job=job, **question_data)

        return job


class EmployerSerializer(serializers.ModelSerializer):
    """Serializer for Employer model.

    Includes user details and profile picture URL, with read-only fields.
    """

    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    profile_pic = serializers.SerializerMethodField()

    class Meta:
        model = Employer
        fields = [
            'profile_pic', 'user_id', 'user_email', 'phone', 'id', 'industry',
            'user_full_name', 'headquarters', 'address', 'about', 'website_link'
        ]

    def get_profile_pic(self, obj):
        """Get the absolute URL of the employer's profile picture.

        Args:
            obj (Employer): Employer instance.

        Returns:
            str: Absolute URL of the profile picture or None if not available.
        """
        if obj.profile_pic:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_pic.url)
            return f"{self.context.get('MEDIA_URL', '')}{obj.profile_pic.url}"
        return None


class JobSerializer(serializers.ModelSerializer):
    """Serializer for Jobs model.

    Includes employer details, questions, application count, and edit permission.
    """

    employer = EmployerSerializer()
    questions = serializers.SerializerMethodField()
    applications_count = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    is_closed = serializers.SerializerMethodField()

    class Meta:
        model = Jobs
        fields = '__all__'
    def get_is_closed(self, obj):
        return obj.is_closed

    def get_questions(self, obj):
        """Get serialized questions associated with the job.

        Args:
            obj (Jobs): Job instance.

        Returns:
            list: Serialized question data.
        """
        questions = Question.objects.filter(job=obj)
        return QuestionSerializer(questions, many=True).data

    def get_applications_count(self, obj):
        """Get the number of applications for the job.

        Args:
            obj (Jobs): Job instance.

        Returns:
            int: Count of applications.
        """
        return ApplyedJobs.objects.filter(job=obj).count()

    def get_can_edit(self, obj):
        """Determine if the current user can edit the job.

        Args:
            obj (Jobs): Job instance.

        Returns:
            bool: True if the user can edit, False otherwise.
        """
        request = self.context.get('request')
        if request:
            return obj.employer.user == request.user or request.user.is_staff
        return False


class EducationSerializer(serializers.ModelSerializer):
    """Serializer for Education model.

    Serializes all fields of the education record.
    """

    class Meta:
        model = Education
        fields = '__all__'


class CandidateSerializer(serializers.ModelSerializer):
    """Serializer for Candidate model.

    Includes education details and user information.
    """

    education = serializers.SerializerMethodField()
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Candidate
        fields = '__all__'

    def get_education(self, obj):
        """Get serialized education records for the candidate.

        Args:
            obj (Candidate): Candidate instance.

        Returns:
            list: Serialized education data.
        """
        educations = Education.objects.filter(user=obj.user)
        return EducationSerializer(educations, many=True).data


class AnswerSerializer(serializers.ModelSerializer):
    """Serializer for Answer model.

    Includes question text as a read-only field.
    """

    question_text = serializers.CharField(source='question.text', read_only=True)

    class Meta:
        model = Answer
        fields = ['id', 'candidate', 'question', 'question_text', 'answer_text']


class ApplyedForJobsSerializer(serializers.ModelSerializer):
    """Serializer for ApplyedJobs model.

    Includes candidate details and their answers.
    """

    candidate = CandidateSerializer()
    answers = serializers.SerializerMethodField()

    class Meta:
        model = ApplyedJobs
        fields = '__all__'

    def get_answers(self, obj):
        """Get serialized answers for the applied job.

        Args:
            obj (ApplyedJobs): Applied job instance.

        Returns:
            list: Serialized answer data.
        """
        answers = Answer.objects.filter(candidate=obj.candidate,
                                       question__job=obj.job)
        return AnswerSerializer(answers, many=True, context=self.context).data


class ApplicationSerializer(serializers.ModelSerializer):
    """Serializer for Jobs model with application details.

    Includes employer name, ID, applications, and questions.
    """

    employer_name = serializers.SerializerMethodField()
    employer_id = serializers.SerializerMethodField()
    applications = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()

    class Meta:
        model = Jobs
        fields = '__all__'

    def get_employer_name(self, obj):
        """Get the employer's full name.

        Args:
            obj (Jobs): Job instance.

        Returns:
            str: Employer's full name.
        """
        return obj.employer.user.full_name

    def get_employer_id(self, obj):
        """Get the employer's ID.

        Args:
            obj (Jobs): Job instance.

        Returns:
            int: Employer's ID.
        """
        return obj.employer.id

    def get_applications(self, obj):
        """Get serialized applications for the job.

        Args:
            obj (Jobs): Job instance.

        Returns:
            list: Serialized application data.
        """
        applications = ApplyedJobs.objects.filter(job=obj)
        serializer = ApplyedForJobsSerializer(applications, many=True)
        return serializer.data

    def get_questions(self, obj):
        """Get serialized questions for the job.

        Args:
            obj (Jobs): Job instance.

        Returns:
            list: Serialized question data.
        """
        questions = Question.objects.filter(job=obj)
        return QuestionSerializer(questions, many=True).data


class SavedJobSerializer(serializers.ModelSerializer):
    """Serializer for SavedJobs model.

    Includes job details.
    """

    job = JobSerializer()

    class Meta:
        model = SavedJobs
        fields = '__all__'


class ApprovalSerializer(serializers.ModelSerializer):
    """Serializer for Approvals model.

    Serializes basic approval fields.
    """

    class Meta:
        model = Approvals
        fields = ['id', 'candidate', 'employer', 'job', 'is_approved',
                  'is_rejected']


class ApplyedJobSerializer(serializers.ModelSerializer):
    """Serializer for ApplyedJobs model with job and candidate details.

    Includes job details and candidate name.
    """

    job = JobSerializer()
    candidate_name = serializers.SerializerMethodField()

    class Meta:
        model = ApplyedJobs
        fields = ['id', 'job', 'status', 'candidate', 'applyed_on',
                  'candidate_name']

    def get_candidate_name(self, obj):
        """Get the candidate's full name.

        Args:
            obj (ApplyedJobs): Applied job instance.

        Returns:
            str: Candidate's full name.
        """
        candidate = Candidate.objects.get(id=obj.candidate_id)
        return candidate.user.full_name


class ApprovalsSerializer(serializers.ModelSerializer):
    """Serializer for Approvals model with nested candidate and employer data."""

    candidate = CandidateSerializer()
    employer = EmployerSerializer()

    class Meta:
        model = Approvals
        fields = ['id', 'candidate', 'employer', 'message', 'is_requested',
                  'is_approved', 'is_rejected', 'requested_at']


class JobSuggestionSerializer(serializers.ModelSerializer):
    """Serializer for Jobs model with suggestion fields."""

    class Meta:
        model = Jobs
        fields = ['title', 'location', 'jobtype', 'jobmode', 'industry',
                  'profile_pic']


class SearchSerializer(serializers.ModelSerializer):
    """Serializer for Jobs model with employer and profile picture details.

    Includes employer name and profile picture URL with fallback logic.
    """

    employer = EmployerSerializer(read_only=True)
    employer_name = serializers.SerializerMethodField()
    profile_pic = serializers.SerializerMethodField()

    class Meta:
        model = Jobs
        fields = [
            'id', 'title', 'location', 'lpa', 'jobtype', 'jobmode', 'experience',
            'applyBefore', 'posteDate', 'about', 'responsibility', 'active',
            'industry', 'employer', 'employer_name', 'profile_pic',
        ]

    def get_employer_name(self, obj):
        """Get the employer's full name with fallback.

        Args:
            obj (Jobs): Job instance.

        Returns:
            str: Employer's full name or "Unnamed Employer" if unavailable.
        """
        try:
            return (obj.employer.user.full_name if obj.employer and
                    obj.employer.user else "Unnamed Employer")
        except Exception as e:
            logger.error(f"Error getting employer_name for job {obj.id}: {str(e)}")
            return "Unnamed Employer"

    def get_profile_pic(self, obj):
        """Get the absolute URL of the employer's profile picture.

        Args:
            obj (Jobs): Job instance.

        Returns:
            str: Absolute URL of the profile picture or default URL if unavailable.
        """
        default_url = "/media/company_pic/default.png"  
        try:
            if not obj.employer:
                logger.warning(f"No employer for job {obj.id}: {obj.title}")
                return default_url
            if obj.employer.profile_pic:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(obj.employer.profile_pic.url)
                return f"{self.context.get('MEDIA_URL', '')}{obj.employer.profile_pic.url}"
            logger.info(f"No profile_pic for job {obj.title}")
            return default_url
        except Exception as e:
            logger.error(f"Error building profile_pic for job {obj.title}: {str(e)}")
            return default_url