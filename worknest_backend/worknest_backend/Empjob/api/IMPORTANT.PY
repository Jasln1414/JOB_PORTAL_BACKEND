# Standard library imports
import logging
import os
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.db.models import Q
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from .serializer import *
logger = logging.getLogger(__name__)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
import razorpay
from django_filters import rest_framework as filters # type: ignore
from django_filters.rest_framework import DjangoFilterBackend # type: ignore
from .serializer import *
from user_account.models import *
from Empjob.models import *
from payment.models import *
from chat.models import *
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
from django.middleware.csrf import get_token
from django.http import JsonResponse

def csrf_token_view(request):
    token = get_token(request)
    return JsonResponse({'csrfToken': token})

# Utility Views
@ensure_csrf_cookie
def get_csrf_token(request):
    return JsonResponse({'csrfToken': get_token(request)})



class PostJob(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            user = request.user
            if user.user_type != 'employer':
                return Response({"error": "Only employers can post jobs"}, status=status.HTTP_403_FORBIDDEN)
            
            employer = Employer.objects.get(user=user)
            #job_count = Jobs.objects.filter(employer=employer).count()
            
            # Check for active subscription
            active_subscription = EmployerSubscription.objects.filter(
                employer=employer, 
                status='active',


                end_date__gt=timezone.now()
            ).first()
            
            # If no active subscription or job limit reached
            if not active_subscription:
                return Response({
                    "error": "No active subscription found",
                    "subscription_required": True,
                    "message": "Please subscribe to post jobs"
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            # If job limit reached based on subscription plan
            if  active_subscription.subscribed_job >= active_subscription.plan.job_limit:

                # For unlimited plans (job_limit = 9999)
                if active_subscription.plan.job_limit == 9999:
                    pass  # Allow posting, no limit
                else:
                    # Check if payment for additional job is provided
                    if 'razorpay_payment_id' not in request.data:
                        order = razorpay_client.order.create({
                            "amount": 200 * 100,  # Additional job posting fee
                            "currency": "INR",
                            "payment_capture": 1
                        })
                        return Response({
                            "payment_required": True,
                            "message": f"You've reached your plan limit of {active_subscription.plan.job_limit} jobs. Payment required for additional job posting.",
                            "order_id": order['id'],
                            "amount": order['amount'],
                            "key": settings.RAZORPAY_KEY_ID
                        }, status=status.HTTP_402_PAYMENT_REQUIRED)
                    
                    # Verify the payment
                    payment_id = request.data['razorpay_payment_id']
                    if not Payment.objects.filter(
                        transaction_id=payment_id,
                        employer=employer,
                        status='success'
                    ).exists():
                        return Response({"error": "Invalid or unverified payment"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Process the job posting
            serializer = PostJobSerializer(data=request.data, context={'employer': employer})
            if serializer.is_valid():
                job = serializer.save()
                active_subscription.subscribed_job+=1
                active_subscription.save()
                
                # Log the job creation with subscription info
                logger.info(f"Job posted by employer {employer.id} with subscription {active_subscription.id if active_subscription else 'None'}")
                
                return Response({"message": "Job posted successfully"}, status=status.HTTP_201_CREATED)
            
            logger.error(f"Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Employer.DoesNotExist:
            return Response({"error": "Employer profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error in PostJob: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from django.utils import timezone
 

def get_employer_job_usage(employer):
    """
    Get job usage statistics for an employer
    
    Returns:
        dict: Contains job count, subscription info, and remaining job slots
    """
    # Get current active subscription
    active_subscription = EmployerSubscription.objects.filter(
        employer=employer,
        status='active',
        end_date__gt=timezone.now()
    ).first()
    
    # Count jobs posted by the employer
    job_count = Jobs.objects.filter(employer=employer).count()
    
    # Default values if no active subscription
    remaining_jobs = 0
    plan_name = None
    plan_limit = 0
    
    if active_subscription:
        plan_name = active_subscription.plan.get_name_display()
        plan_limit = active_subscription.plan.job_limit
        
        # Calculate remaining job slots
        if plan_limit == 9999:  # Unlimited
            remaining_jobs = "Unlimited"
        else:
            remaining_jobs = max(0, plan_limit - job_count)
    
    return {
        "job_count": job_count,
        "has_active_subscription": bool(active_subscription),
        "subscription_plan": plan_name,
        "job_limit": plan_limit,
        "remaining_jobs": remaining_jobs,
        "subscription_end_date": active_subscription.end_date if active_subscription else None
    }



class JobUsageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.info("JobUsageView endpoint hit!")
        try:
            user = request.user
            if not hasattr(user, 'user_type') or user.user_type != 'employer':
                return Response({"error": "Only employers can access this information"}, status=status.HTTP_403_FORBIDDEN)

            employer = Employer.objects.get(user=user)
            subscription = EmployerSubscription.objects.filter(
                employer=employer, status="active", end_date__gt=timezone.now()
            ).order_by('-start_date').first()
            job_count = Jobs.objects.filter(employer=employer, active=True).count()
            #job_count=
            
            if subscription:
              
                # Use the subscription's job_limit consistently
                Subscribed_job_count=subscription.subscribed_job
                job_limit = subscription.job_limit
                remaining_jobs = "Unlimited" if job_limit == 9999 else max(0, job_limit - Subscribed_job_count)
                usage_stats = {
                    "job_count": job_count,
                    "has_active_subscription": True,
                    "subscription_plan": subscription.plan.name,
                    "job_limit": job_limit,
                    "remaining_jobs": remaining_jobs,
                    "subscription_end_date": subscription.end_date.isoformat()
                }
            else:
               
                usage_stats = {
                    "job_count": job_count,
                    "has_active_subscription": False,
                    "subscription_plan": None,
                    "job_limit": 0,
                    "remaining_jobs": 0,
                    "subscription_end_date": None
                }

            logger.info(f"Returning usage stats: {usage_stats}")
            return Response(usage_stats, status=status.HTTP_200_OK)
        except Employer.DoesNotExist:
            return Response({"error": "Employer profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error in JobUsageView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)







class EditJob(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        jobId = request.data.get("jobId")
        try:
            job = Jobs.objects.get(id=jobId)
        except Jobs.DoesNotExist:
            return Response({"message":"something went wrong"}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
        
        serializer = PostJobSerializer(instance=job, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_400_BAD_REQUEST)

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            candidate = Candidate.objects.get(user=user)
            serializer = CandidateSerializer(candidate, context={'request': request})
            return Response({
                'user_type': 'candidate',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            try:
                employer = Employer.objects.get(user=user)
               
                serializer = EmployerSerializer(employer, context={'request': request})
                print("............................................................",serializer)
                return Response({
                    'user_type': 'employer',
                    'data': serializer.data
                }, status=status.HTTP_200_OK)
            except Employer.DoesNotExist:
                return Response({
                    "message": "User profile not found",
                    "detail": "No candidate or employer profile exists for this user"
                }, status=status.HTTP_404_NOT_FOUND)


class GetJob(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        try:
            employer = Employer.objects.get(user=user)
            jobs = Jobs.objects.filter(employer=employer)
            serializer = JobSerializer(jobs, many=True)
            data = {
                "data": serializer.data
            }
            return Response(data, status=status.HTTP_200_OK)
        except Employer.DoesNotExist:
            return Response({"error": "Employer not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetAllJob(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Check if the user is an employer
            if request.user.user_type == "employer":
                # Fetch the employer instance linked to the user
                employer = Employer.objects.get(user=request.user)
                # Filter jobs by the employer
                jobs = Jobs.objects.filter(employer=employer)
            else:
                # User is a candidate or admin: return all jobs
                jobs = Jobs.objects.all()

            serializer = JobSerializer(jobs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Employer.DoesNotExist:
            return Response({"error": "Employer profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetJobDetail(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, job_id):
        try:
            # Get the job with related employer data
            job = Jobs.objects.select_related('employer', 'employer__user').get(id=job_id)
            
            # Pass the request to serializer for absolute URLs
            serializer = JobSerializer(job, context={'request': request})
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Jobs.DoesNotExist:
            return Response(
                {"error": "Job not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error in GetJobDetail: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while fetching job details"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class GetApplyedjob(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            candidate = Candidate.objects.get(user=user)
            applied_jobs = ApplyedJobs.objects.filter(candidate=candidate)
            serializer = ApplyedJobSerializer(applied_jobs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            return Response({"message": "Candidate not found"}, status=404)
        except Exception as e:
            return Response({"message": str(e)}, status=500)
        


    def post(self, request, approve_id):
        return Response({"message": "Chat request approved"}, status=status.HTTP_200_OK)

class GetApplicationjob(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        try:
            employer = Employer.objects.get(user=user)
            jobs = Jobs.objects.filter(employer=employer, active=True)
            serializer = ApplicationSerializer(jobs, many=True)
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SearchSerializer(serializers.ModelSerializer):
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
        try:
            return obj.employer.user.full_name if obj.employer and obj.employer.user else "Unnamed Employer"
        except Exception as e:
            print(f"[Serializer] Error getting employer_name for job {obj.id}: {str(e)}")
            return "Unnamed Employer"

    def get_profile_pic(self, obj):
        default_url = "http://127.0.0.1:8000/media/company_pic/default.png"
        try:
            if not obj.employer:
                print(f"[Serializer] No employer for job {obj.id}: {obj.title}")
                return default_url
            if obj.employer.profile_pic:
                request = self.context.get('request')
                media_root = self.context.get('settings', {}).get('MEDIA_ROOT', '')
                file_path = os.path.join(media_root, str(obj.employer.profile_pic))
                # Check if file exists
                if media_root and not os.path.exists(file_path):
                    print(f"[Serializer] Image missing for {obj.title}: {file_path}")
                    return default_url
                # Build URL
                if request:
                    url = request.build_absolute_uri(obj.employer.profile_pic.url)
                else:
                    url = f"http://127.0.0.1:8000{obj.employer.profile_pic.url}"
                print(f"[Serializer] Profile pic for {obj.title}: {url}")
                return url
            print(f"[Serializer] No profile_pic for {obj.title}")
            return default_url
        except Exception as e:
            print(f"[Serializer] Error building profile_pic for {obj.title}: {str(e)}")
            return default_url



class JobFilter(filters.FilterSet):
    """
    FilterSet for Jobs model with enhanced filtering capabilities.
    """
    search = filters.CharFilter(method='filter_search', label='Search')
    location = filters.CharFilter(method='filter_location', label='Location')
    jobtype = filters.CharFilter(lookup_expr='iexact', label='Job Type')
    jobmode = filters.CharFilter(method='filter_jobmode', label='Job Mode')
    experience = filters.CharFilter(lookup_expr='iexact', label='Experience')
    lpa = filters.CharFilter(method='filter_lpa', label='Salary Range (e.g., 10-20)')
    employer = filters.NumberFilter(field_name='employer__id', label='Employer ID')
    industry = filters.CharFilter(lookup_expr='icontains', label='Industry')
    active = filters.BooleanFilter(field_name='active', label='Active Jobs Only')
    recent = filters.CharFilter(method='filter_recent', label='Recent Jobs')
    skills = filters.CharFilter(method='filter_skills', label='Required Skills')
    
    class Meta:
        model = Jobs
        fields = ['search', 'location', 'jobtype', 'jobmode', 'experience', 
                 'lpa', 'employer', 'industry', 'active', 'recent', 'skills']
    
    def filter_search(self, queryset, name, value):
        """
        Enhanced search across multiple job fields with keyword relevance.
        """
        if not value:
            return queryset
            
        search_terms = value.split()
        query = Q()
        
        for term in search_terms:
            query |= (
                Q(title__icontains=term) |  
                Q(about__icontains=term) | 
                Q(responsibility__icontains=term) | 
                Q(employer__user__full_name__icontains=term)
            )
            
        return queryset.filter(query).select_related('employer').distinct()
    
    def filter_location(self, queryset, name, value):
        if not value:
            return queryset
        
        value_lower = value.lower().strip()
        
        if value_lower == "remote":
            return queryset.filter(
                Q(location__iexact="remote") | 
                Q(jobmode__iexact="remote")
            )
        
        exact_match = queryset.filter(location__iexact=value)
        if exact_match.exists():
            return exact_match
            
        return queryset.filter(location__icontains=value)
    
    def filter_jobmode(self, queryset, name, value):
        if not value:
            return queryset
        prefix = value[:3].lower()
        return queryset.filter(jobmode__istartswith=prefix)
    
    def filter_lpa(self, queryset, name, value):
        if not value:
            return queryset
            
        try:
            if value.endswith('+'):
                min_lpa = float(value.rstrip('+'))
                return queryset.filter(lpa__gte=min_lpa)
                
            if '-' in value:
                min_lpa, max_lpa = map(float, value.split('-'))
                return queryset.filter(
                    Q(lpa__startswith=f"{int(min_lpa)}-") | 
                    Q(lpa__endswith=f"-{int(max_lpa)}") |
                    Q(lpa__gte=min_lpa, lpa__lte=max_lpa)
                )
                
            return queryset.filter(lpa=value)
        except (ValueError, TypeError):
            return queryset
    
    def filter_recent(self, queryset, name, value):
        if not value:
            return queryset
            
        now = timezone.now()
        
        if value == 'today' or value == '24h':
            start_date = now - timedelta(days=1)
        elif value == 'week' or value == '7d':
            start_date = now - timedelta(days=7)
        elif value == 'month' or value == '30d':
            start_date = now - timedelta(days=30)
        else:
            return queryset
            
        return queryset.filter(posteDate__gte=start_date)
        
    def filter_skills(self, queryset, name, value):
        if not value:
            return queryset
            
        skills = [skill.strip().lower() for skill in value.split(',')]
        query = Q()
        
        for skill in skills:
            if not skill:
                continue
                
            query |= (
                Q(title__icontains=skill) |
                Q(about__icontains=skill) |
                Q(responsibility__icontains=skill)
            )
            
        return queryset.filter(query).distinct()
    
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from Empjob.models import Jobs



class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class JobSearchView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Jobs.objects.select_related('employer').filter(active=True).order_by('-posteDate')
    serializer_class = SearchSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = JobFilter
    pagination_class = StandardResultsSetPagination

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({
            'request': self.request,
            'settings': {'MEDIA_ROOT': settings.MEDIA_ROOT}
        })
        return context

class GetAllJobsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Jobs.objects.select_related('employer').filter(active=True).order_by('-posteDate')
    serializer_class = SearchSerializer
    pagination_class = StandardResultsSetPagination

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({
            'request': self.request,
            'settings': {'MEDIA_ROOT': settings.MEDIA_ROOT}
        })
        return context

class JobAutocompleteView(APIView):
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)
        suggestions = []
        try:
            titles = Jobs.objects.filter(
                Q(title__icontains=query) & Q(active=True)
            ).values('title').distinct()[:5]
            suggestions.extend([{'type': 'title', 'value': t['title']} for t in titles])

            locations = Jobs.objects.filter(
                Q(location__icontains=query) & Q(active=True)
            ).values('location').distinct()[:5]
            suggestions.extend([{'type': 'location', 'value': l['location']} for l in locations])

            jobtypes = Jobs.objects.filter(
                Q(jobtype__icontains=query) & Q(active=True)
            ).values('jobtype').distinct()[:5]
            suggestions.extend([{'type': 'jobtype', 'value': j['jobtype']} for j in jobtypes])

            jobmodes = Jobs.objects.filter(
                Q(jobmode__icontains=query) & Q(active=True)
            ).values('jobmode').distinct()[:5]
            suggestions.extend([{'type': 'jobmode', 'value': j['jobmode']} for j in jobmodes])

            industries = Jobs.objects.filter(
                Q(industry__icontains=query) & Q(active=True)
            ).values('industry').distinct()[:5]
            suggestions.extend([{'type': 'industry', 'value': i['industry']} for i in industries])
        except Exception as e:
            print(f"[Autocomplete] Error fetching suggestions: {str(e)}")

        suggestions = sorted(suggestions, key=lambda x: x['value'].lower())[:10]
        return Response(suggestions, status=status.HTTP_200_OK)

class GetJobStatus(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        action = request.data.get('action')
        try:
            job = Jobs.objects.get(id=job_id)
            
            if job.employer.user != request.user and not request.user.is_staff:
                return Response(
                    {"error": "You don't have permission to modify this job"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if action == 'deactivate':
                job.active = False
                message = "Job deactivated successfully"
            elif action == 'activate':
                job.active = True
                message = "Job activated successfully"
            else:
                return Response(
                    {"error": "Invalid action. Use 'activate' or 'deactivate'"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            job.save()
            serializer = JobSerializer(job, context={'request': request})
            return Response({
                "message": message,
                "job": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Jobs.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)


from django.shortcuts import get_object_or_404



class SavejobStatus(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, job_id):
        action = request.data.get('action')
        user = request.user
        
        if action not in ['save', 'unsave']:
            return Response(
                {"error": "Invalid action. Use 'save' or 'unsave'"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            job = get_object_or_404(Jobs, id=job_id)
            candidate = get_object_or_404(Candidate, user=user)
            
            if action == 'save':
                saved_job, created = SavedJobs.objects.get_or_create(
                    candidate=candidate, 
                    job=job
                )
                return Response(
                    {"message": "Job saved successfully" if created else "Job already saved"},
                    status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
                )
                
            elif action == 'unsave':
                deleted_count, _ = SavedJobs.objects.filter(
                    candidate=candidate, 
                    job=job
                ).delete()
                if deleted_count > 0:
                    return Response(
                        {"message": "Job unsaved successfully"}, 
                        status=status.HTTP_200_OK
                    )
                return Response(
                    {"message": "Job was not saved"}, 
                    status=status.HTTP_200_OK
                )
                    
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CheckJobSaveStatus(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, job_id):
        user = request.user
        print("...................................",user)
        try:
            job = Jobs.objects.get(id=job_id)
            candidate = Candidate.objects.get(user=user)
            is_saved = SavedJobs.objects.filter(candidate=candidate, job=job).exists()
            return Response({"is_saved": is_saved}, status=status.HTTP_200_OK)
        except Jobs.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
        except Candidate.DoesNotExist:
            return Response({"error": "Candidate not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SavedJobsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            candidate = get_object_or_404(Candidate, user=request.user)
            saved_jobs = SavedJobs.objects.filter(candidate=candidate)
            serializer = SavedJobSerializer(saved_jobs, many=True)
            return Response(
                {"data": serializer.data}, 
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class ApplicationStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, job_id):
        action = request.data.get('action')
        try:
            applied_job = ApplyedJobs.objects.get(id=job_id)
            job_name = applied_job.job.title
            receiver = applied_job.candidate.user

            print("applied job....",job_name, "user....",receiver.id)
            if applied_job:
                applied_job.status = action
                applied_job.save()
                
                message = f'Application status for job {job_name} changed to {action}'
                notifications = Notifications.objects.create(user = receiver,message = message)
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'notification_{receiver.id}',
                    {
                        'type': 'notify_message',
                        'message': {
                            'text': message,
                            'sender': "employer",
                            'is_read': False,
                            'timestamp': datetime.now().isoformat(),
                            'chat_id': None
                        },
                        'unread_count': 1
                    }
                )
                return Response({"message": "Status changed"}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No job available"}, status=status.HTTP_204_NO_CONTENT)
        except ApplyedJobs.DoesNotExist:
            return Response({"error": "Job application not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class GetQuestions(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, job_id):
        try:
            questions = Question.objects.filter(job=job_id)
            serializer = QuestionSerializer(questions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response(status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
        


class Applyjob(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, job_id):
        user = request.user
        try:
            job = Jobs.objects.get(id=job_id)
            employer = User.objects.get(id=job.employer.user.id)
            candidate = Candidate.objects.get(user=user)
            if ApplyedJobs.objects.filter(candidate=candidate, job=job).exists():
                return Response({'message': 'You have already applied for this job.'}, status=status.HTTP_200_OK)
            
            application = ApplyedJobs.objects.create(candidate=candidate, job=job)
            
            answers_data = request.data.get('answers', [])
            for answer in answers_data:
                question_id = answer.get('question')
                answer_text = answer.get('answer_text')
                try:
                    question = Question.objects.get(id=question_id, job=job)
                    Answer.objects.create(
                        candidate=candidate,
                        question=question,
                        answer_text=answer_text,
                        question_text=question.text  # Save the question text here
                    )
                except Question.DoesNotExist:
                    return Response({'message': f'Question {question_id} not found.'}, status=status.HTTP_400_BAD_REQUEST)
            message = f"{candidate} is applyed for the job you posted {job.title}."
            notifications = Notifications.objects.create(user = employer,message = message)
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notification_{employer.id}',
                {
                    'type': 'notify_message',
                    'message': {
                        'text': message,
                        'sender': "employer",
                        'is_read': False,
                        'timestamp': datetime.now().isoformat(),
                        'chat_id': None
                    },
                    'unread_count': 1
                }
            )
            return Response({'message': 'You have successfully applied for the job.'}, status=status.HTTP_200_OK)
        except Jobs.DoesNotExist:
            return Response({'message': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Candidate.DoesNotExist:
            return Response({'message': 'Candidate not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, candidate_id, employer_id):
        candidate = Candidate.objects.get(id=candidate_id)
        employer = Employer.objects.get(id=employer_id)
        print("inside approval job....", candidate, employer)
        try:
            approvals = Approvals.objects.get(candidate=candidate, employer=employer)
            print("inside approval job....", approvals)
            serializer = ApprovalsSerializer(approvals)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ChatApprovalView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, approvalId):
        message = request.data.get('message')
        action = request.data.get('action')
        approval = Approvals.objects.get(id=approvalId)
        candidate =Candidate.objects.get(id = approval.candidate.id)
        employer = Employer.objects.get(id = approval.employer.id) 
        print("inside approval job....", candidate, employer, approval)
        try:
            if action == "requested":
                approval.is_requested = True
                approval.is_approved = False
                approval.is_rejected = False
                approval.message = message
                notification_message = f"{candidate} is requested for chat approval with a message - {message}."
                reciverid = employer.user.id
                notification_user = User.objects.get(id = reciverid)
                print("inside chat approval request,",notification_message, reciverid, notification_user)
            elif action == "approved":
                approval.is_requested = False
                approval.is_approved = True
                approval.is_rejected = False
                notification_message = f"{employer} is approved your chat request you can now send messages."
                reciverid = candidate.user.id
                notification_user = User.objects.get(id = reciverid)
            elif action == "rejected": 
                approval.is_requested = False
                approval.is_approved = False
                approval.is_rejected = True
                notification_message = f"{employer} is rejected your chat request."
                reciverid = candidate.user.id
                notification_user = User.objects.get(id = reciverid)
            notifications = Notifications.objects.create(user = notification_user,message = notification_message)
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notification_{reciverid}',
                {
                    'type': 'notify_message',
                    'message': {
                        'text': notification_message,
                        'sender': "employer",
                        'is_read': False,
                        'timestamp': datetime.now().isoformat(),
                        'chat_id': None
                    },
                    'unread_count': 1
                }
            )
            approval.save()
            return Response({"message": "Approval status updated successfully"}, status=status.HTTP_200_OK)
        except Approvals.DoesNotExist:
            return Response({"error": "Approval not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_application(request, job_id):
    has_applied = ApplyedJobs.objects.filter(job_id=job_id, candidate__user=request.user).exists()
    return Response({"has_applied": has_applied})




