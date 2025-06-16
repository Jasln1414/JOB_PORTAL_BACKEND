from rest_framework import serializers
from Interview.models import *
from Empjob.models import *
from Empjob.api.serializer import JobSerializer

class SheduleInterviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewShedule
        fields = ['id','candidate', 'employer', 'job', 'date']
        read_only_fields = ['employer']

    def create(self, validated_data): 
        request = self.context.get('request')
        user = request.user
        employer = Employer.objects.get(user=user)
        validated_data['employer'] = employer
        return super().create(validated_data)

class InterviewSheduleSerializer(serializers.ModelSerializer):
    employer_name = serializers.SerializerMethodField()
    candidate_name = serializers.SerializerMethodField()
    apply_date = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    job_info = serializers.SerializerMethodField()

    class Meta:
        model = InterviewShedule
        fields = [
            'id', 'candidate', 'employer', 'job', 'date',
            'active', 'selected', 'status', 'employer_name',
            'apply_date', 'candidate_name', 'job_title', 'job_info','attended'
        ]

    def get_job_info(self, obj):
        job = obj.job
        if not job:
            return {}
            
        return {
            "title": job.title,
            "id": job.id,
            "location": job.location,
            "experience": job.experience,
            "lpa": job.lpa,
            
        }
    
   
    def get_employer_name(self, obj):
        return obj.employer.user.full_name if obj.employer.user else ''
    
    def get_apply_date(self, obj):
        try:
            return ApplyedJobs.objects.get(
                job=obj.job,
                candidate=obj.candidate
            ).applyed_on
        except ApplyedJobs.DoesNotExist:
            return None
    
    def get_candidate_name(self, obj):
        return obj.candidate.user.full_name if obj.candidate.user else ''
    
    def get_job_title(self, obj):
        return obj.job.title if obj.job else ''
    

