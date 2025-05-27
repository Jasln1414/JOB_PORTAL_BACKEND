"""Module for handling job posting, application, and user profile views.

This module provides API endpoints for job management, application processes,
user profiles, and payment-related actions using Django REST Framework.
"""

# Standard library imports
import logging
import os
from datetime import datetime, timedelta

# Django imports
from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Q

# Third-party imports
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from django_filters.rest_framework import DjangoFilterBackend # type: ignore
import razorpay
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Local app imports
from .serializer import (
    PostJobSerializer, EmployerSerializer, JobSerializer, CandidateSerializer,
    ApplyedJobSerializer, ApplicationSerializer, QuestionSerializer, SavedJobSerializer,
    ApprovalsSerializer, SearchSerializer
)
from user_account.models import Employer, Candidate, User
from Empjob.models import Jobs, Question, Answer, ApplyedJobs, SavedJobs, Approvals
from payment.models import EmployerSubscription, Payment
from chat.models import Notifications

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


def csrf_token_view(request):
    """Return the CSRF token for the request.

    Args:
        request: HTTP request object.

    Returns:
        JsonResponse: Response containing the CSRF token.
    """
    token = get_token(request)
    return JsonResponse({'csrfToken': token})


@ensure_csrf_cookie
def get_csrf_token(request):
    """Set and return the CSRF token in a cookie.

    Args:
        request: HTTP request object.

    Returns:
        JsonResponse: Response containing the CSRF token.
    """
    return JsonResponse({'csrfToken': get_token(request)})


def get_employer_job_usage(employer):
    """Get job usage statistics for an employer.

    Args:
        employer (Employer): Employer instance.

    Returns:
        dict: Contains job count, subscription info, and remaining job slots.
    """
    active_subscription = EmployerSubscription.objects.filter(
        employer=employer,
        status='active',
        end_date__gt=timezone.now()
    ).first()

    job_count = Jobs.objects.filter(employer=employer).count()

    remaining_jobs = 0
    plan_name = None
    plan_limit = 0

    if active_subscription:
        plan_name = active_subscription.plan.get_name_display()
        plan_limit = active_subscription.plan.job_limit
        remaining_jobs = ("Unlimited" if plan_limit == 9999
                          else max(0, plan_limit - job_count))

    return {
        "job_count": job_count,
        "has_active_subscription": bool(active_subscription),
        "subscription_plan": plan_name,
        "job_limit": plan_limit,
        "remaining_jobs": remaining_jobs,
        "subscription_end_date": (active_subscription.end_date
                                 if active_subscription else None)
    }


class PostJob(APIView):
    """API view to handle job posting by authenticated employers.

    Requires an active subscription or payment for additional job postings.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle POST request to create a new job posting.

        Args:
            request: HTTP request object containing job data.

        Returns:
            Response: JSON response with success message or error details.
        """
        try:
            user = request.user
            if user.user_type != 'employer':
                return Response({"error": "Only employers can post jobs"},
                                status=status.HTTP_403_FORBIDDEN)

            employer = Employer.objects.get(user=user)
            active_subscription = EmployerSubscription.objects.filter(
                employer=employer,
                status='active',
                end_date__gt=timezone.now()
            ).first()

            if not active_subscription:
                return Response({
                    "error": "No active subscription found",
                    "subscription_required": True,
                    "message": "Please subscribe to post jobs"
                }, status=status.HTTP_402_PAYMENT_REQUIRED)

            if (active_subscription.subscribed_job >=
                    active_subscription.plan.job_limit):
                if active_subscription.plan.job_limit == 9999:
                    pass
                else:
                    if 'razorpay_payment_id' not in request.data:
                        order = razorpay_client.order.create({
                            "amount": 200 * 100,
                            "currency": "INR",
                            "payment_capture": 1
                        })
                        return Response({
                            "payment_required": True,
                            "message": (f"You've reached your plan limit of "
                                        f"{active_subscription.plan.job_limit} "
                                        "jobs. Payment required for "
                                        "additional job posting."),
                            "order_id": order['id'],
                            "amount": order['amount'],
                            "key": settings.RAZORPAY_KEY_ID
                        }, status=status.HTTP_402_PAYMENT_REQUIRED)

                    payment_id = request.data['razorpay_payment_id']
                    if not Payment.objects.filter(
                        transaction_id=payment_id,
                        employer=employer,
                        status='success'
                    ).exists():
                        return Response(
                            {"error": "Invalid or unverified payment"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

            serializer = PostJobSerializer(
                data=request.data, context={'employer': employer}
            )
            if serializer.is_valid():
                job = serializer.save()
                active_subscription.subscribed_job += 1
                active_subscription.save()
                logger.info(
                    f"Job posted by employer {employer.id} with subscription "
                    f"{active_subscription.id if active_subscription else 'None'}"
                )
                return Response(
                    {"message": "Job posted successfully"},
                    status=status.HTTP_201_CREATED
                )

            logger.error(f"Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Employer.DoesNotExist:
            return Response(
                {"error": "Employer profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Unexpected error in PostJob: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class JobUsageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.info(f"JobUsageView endpoint hit! User ID: {request.user.id}")
        try:
            user = request.user
            logger.info(f"User: {user.id}, user_type: {getattr(user, 'user_type', 'N/A')}")
            
            if not hasattr(user, 'user_type') or user.user_type.lower() != 'employer':
                logger.error("User is not an employer")
                return Response({"error": "Only employers can access this information"}, status=status.HTTP_403_FORBIDDEN)

            employers = Employer.objects.filter(user=user)
            if not employers.exists():
                logger.error(f"No employer profiles found for user_id: {user.id}")
                return Response({"error": "Employer profile not found"}, status=status.HTTP_404_NOT_FOUND)

            employer_ids = [e.id for e in employers]

            # Get active subscription
            subscription = EmployerSubscription.objects.filter(
                employer__in=employers,
                status__iexact="active",
                end_date__gt=timezone.now()
            ).order_by('-start_date').first()

            # Determine if active subscription is near expiry
            is_near_expiry = False
            if subscription:
                days_until_expiry = (subscription.end_date - timezone.now()).days
                is_near_expiry = days_until_expiry <= 7  # Show renewal button if less than or equal to 7 days remaining

            # Get renewal subscription (regardless of active state)
            renewal_subscription = EmployerSubscription.objects.filter(
                employer__in=employers,
                status__in=["expired", "cancelled", "inactive"]
            ).order_by('-end_date').first()

            # Include renewal subscription details only if necessary
            if not subscription or is_near_expiry:
                renewal_subscription_id = renewal_subscription.razorpay_subscription_id if renewal_subscription else None
                renewal_subscription_plan = renewal_subscription.plan.name if renewal_subscription else None
                renewal_subscription_end_date = renewal_subscription.end_date.isoformat() if renewal_subscription else None
            else:
                renewal_subscription_id = None
                renewal_subscription_plan = None
                renewal_subscription_end_date = None

            job_count = Jobs.objects.filter(employer__in=employers, active=True).count()

            if subscription:
                subscribed_job_count = subscription.subscribed_job
                job_limit = subscription.plan.job_limit
                remaining_jobs = "Unlimited" if job_limit == 9999 else max(0, job_limit - subscribed_job_count)
                usage_stats = {
                    "job_count": job_count,
                    "has_active_subscription": True,
                    "subscription_plan": subscription.plan.name,
                    "job_limit": job_limit,
                    "remaining_jobs": remaining_jobs,
                    "subscription_end_date": subscription.end_date.isoformat(),
                    "subscription_status": subscription.status,
                    "existing_subscription_id": subscription.razorpay_subscription_id,
                    "renewal_subscription_id": renewal_subscription_id,
                    "renewal_subscription_plan": renewal_subscription_plan,
                    "renewal_subscription_end_date": renewal_subscription_end_date,
                    "is_subscription_near_expiry": is_near_expiry,
                }
            else:
                usage_stats = {
                    "job_count": job_count,
                    "has_active_subscription": False,
                    "subscription_plan": None,
                    "job_limit": 0,
                    "remaining_jobs": 0,
                    "subscription_end_date": None,
                    "subscription_status": None,
                    "existing_subscription_id": None,
                    "renewal_subscription_id": renewal_subscription_id,
                    "renewal_subscription_plan": renewal_subscription_plan,
                    "renewal_subscription_end_date": renewal_subscription_end_date,
                    "is_subscription_near_expiry": False,
                }

            logger.info(f"Returning usage stats: {usage_stats}")
            return Response(usage_stats, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error in JobUsageView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EditJob(APIView):
    """API view to edit an existing job posting."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Handle POST request to update an existing job.

        Args:
            request: HTTP request object containing job data and jobId.

        Returns:
            Response: JSON response with updated job data or error status.
        """
        job_id = request.data.get("jobId")
        try:
            job = Jobs.objects.get(id=job_id)
        except Jobs.DoesNotExist:
            return Response(
                {"message": "something went wrong"},
                status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION
            )

        serializer = PostJobSerializer(instance=job, data=request.data,
                                      partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_400_BAD_REQUEST)


class ProfileView(APIView):
    """API view to retrieve the user's profile based on their type."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Handle GET request to retrieve user profile.

        Args:
            request: HTTP request object.

        Returns:
            Response: JSON response with profile data or error details.
        """
        user = request.user
        try:
            candidate = Candidate.objects.get(user=user)
            serializer = CandidateSerializer(candidate,
                                            context={'request': request})
            return Response({
                'user_type': 'candidate',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            try:
                employer = Employer.objects.get(user=user)
                serializer = EmployerSerializer(employer,
                                               context={'request': request})
                return Response({
                    'user_type': 'employer',
                    'data': serializer.data
                }, status=status.HTTP_200_OK)
            except Employer.DoesNotExist:
                return Response({
                    "message": "User profile not found",
                    "detail": ("No candidate or employer profile exists "
                               "for this user")
                }, status=status.HTTP_404_NOT_FOUND)


class GetJob(APIView):
    """API view to retrieve jobs posted by the authenticated employer."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Handle GET request to retrieve jobs for the employer.

        Args:
            request: HTTP request object.

        Returns:
            Response: JSON response with job data or error details.
        """
        user = request.user
        try:
            employer = Employer.objects.get(user=user)
            jobs = Jobs.objects.filter(employer=employer)
            serializer = JobSerializer(jobs, many=True)
            data = {"data": serializer.data}
            return Response(data, status=status.HTTP_200_OK)
        except Employer.DoesNotExist:
            return Response(
                {"error": "Employer not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetAllJob(APIView):
    """API view to retrieve all jobs based on user type."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Handle GET request to retrieve all jobs.

        Args:
            request: HTTP request object.

        Returns:
            Response: JSON response with job data or error details.
        """
        try:
            if request.user.user_type == "employer":
                employer = Employer.objects.get(user=request.user)
                jobs = Jobs.objects.filter(employer=employer)
            else:
                jobs = Jobs.objects.all()

            serializer = JobSerializer(jobs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Employer.DoesNotExist:
            return Response(
                {"error": "Employer profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetJobDetail(APIView):
    """API view to retrieve details of a specific job."""

    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        """Handle GET request to retrieve job details.

        Args:
            request: HTTP request object.
            job_id (int): ID of the job to retrieve.

        Returns:
            Response: JSON response with job details or error details.
        """
        try:
            job = Jobs.objects.select_related('employer',
                                             'employer__user').get(id=job_id)
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
    """API view to retrieve applied jobs for the authenticated candidate."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Handle GET request to retrieve applied jobs.

        Args:
            request: HTTP request object.

        Returns:
            Response: JSON response with applied job data or error details.
        """
        user = request.user
        try:
            candidate = Candidate.objects.get(user=user)
            applied_jobs = ApplyedJobs.objects.filter(candidate=candidate)
            serializer = ApplyedJobSerializer(
                applied_jobs, many=True, context={'request': request}
            )
            logger.info(f"Serialized applied jobs data: {serializer.data}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            return Response({"message": "Candidate not found"}, status=404)
        except Exception as e:
            logger.error(f"Error in GetApplyedjob: {str(e)}")
            return Response({"message": str(e)}, status=500)

    def post(self, request, approve_id):
        """Handle POST request to approve a chat request (currently a stub).

        Args:
            request: HTTP request object.
            approve_id (int): ID of the approval.

        Returns:
            Response: JSON response with success message.
        """
        return Response({"message": "Chat request approved"},
                        status=status.HTTP_200_OK)


class GetApplicationjob(APIView):
    """API view to retrieve applications for jobs posted by the employer."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Handle GET request to retrieve job applications.

        Args:
            request: HTTP request object.

        Returns:
            Response: JSON response with application data or error details.
        """
        user = request.user
        try:
            employer = Employer.objects.get(user=user)
            jobs = Jobs.objects.filter(employer=employer, active=True)
            serializer = ApplicationSerializer(jobs, many=True)
            return Response({'data': serializer.data},
                            status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StandardResultsSetPagination(PageNumberPagination):
    """Custom pagination class with configurable page size."""

    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


import django_filters # type: ignore


class JobFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    location = django_filters.CharFilter(field_name='location', lookup_expr='icontains')
    job_type = django_filters.CharFilter(field_name='job_type', lookup_expr='exact')

    class Meta:
        model = Jobs
        fields = ['title', 'location', 'job_type']

class JobSearchView(generics.ListAPIView):
    """API view for searching jobs with filtering and pagination."""

    permission_classes = [IsAuthenticated]
    queryset = Jobs.objects.select_related('employer').filter(
        active=True
    ).order_by('-posteDate')
    serializer_class = SearchSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = JobFilter
    pagination_class = StandardResultsSetPagination

    def get_serializer_context(self):
        """Add request and settings context to serializer.

        Returns:
            dict: Updated context with request and media root.
        """
        context = super().get_serializer_context()
        context.update({
            'request': self.request,
            'settings': {'MEDIA_ROOT': settings.MEDIA_ROOT}
        })
        return context


class GetAllJobsView(generics.ListAPIView):
    """API view to retrieve all active jobs with pagination."""

    permission_classes = [IsAuthenticated]
    queryset = Jobs.objects.select_related('employer').filter(
        active=True
    ).order_by('-posteDate')
    serializer_class = SearchSerializer
    pagination_class = StandardResultsSetPagination

    def get_serializer_context(self):
        """Add request and settings context to serializer.

        Returns:
            dict: Updated context with request and media root.
        """
        context = super().get_serializer_context()
        context.update({
            'request': self.request,
            'settings': {'MEDIA_ROOT': settings.MEDIA_ROOT}
        })
        return context


class JobAutocompleteView(APIView):
    """API view for job autocomplete suggestions."""

    def get(self, request):
        """Handle GET request to provide job autocomplete suggestions.

        Args:
            request: HTTP request object with 'q' query parameter.

        Returns:
            Response: JSON response with suggestion list or empty list.
        """
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)
        suggestions = []
        try:
            titles = Jobs.objects.filter(
                Q(title__icontains=query) & Q(active=True)
            ).values('title').distinct()[:5]
            suggestions.extend(
                [{'type': 'title', 'value': t['title']} for t in titles]
            )

            locations = Jobs.objects.filter(
                Q(location__icontains=query) & Q(active=True)
            ).values('location').distinct()[:5]
            suggestions.extend(
                [{'type': 'location', 'value': l['location']} for l in locations]
            )

            jobtypes = Jobs.objects.filter(
                Q(jobtype__icontains=query) & Q(active=True)
            ).values('jobtype').distinct()[:5]
            suggestions.extend(
                [{'type': 'jobtype', 'value': j['jobtype']} for j in jobtypes]
            )

            jobmodes = Jobs.objects.filter(
                Q(jobmode__icontains=query) & Q(active=True)
            ).values('jobmode').distinct()[:5]
            suggestions.extend(
                [{'type': 'jobmode', 'value': j['jobmode']} for j in jobmodes]
            )

            industries = Jobs.objects.filter(
                Q(industry__icontains=query) & Q(active=True)
            ).values('industry').distinct()[:5]
            suggestions.extend(
                [{'type': 'industry', 'value': i['industry']} for i in industries]
            )
        except Exception as e:
            logger.error(f"Error fetching suggestions: {str(e)}")

        suggestions = sorted(suggestions, key=lambda x: x['value'].lower())[:10]
        return Response(suggestions, status=status.HTTP_200_OK)


class GetJobStatus(APIView):
    """API view to manage job activation/deactivation status."""

    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        """Handle POST request to change job status.

        Args:
            request: HTTP request object with 'action' parameter.
            job_id (int): ID of the job to update.

        Returns:
            Response: JSON response with status message and job data.
        """
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
            return Response({"error": "Job not found"},
                            status=status.HTTP_404_NOT_FOUND)


class SavejobStatus(APIView):
    """API view to manage saving/unsaving jobs for candidates."""

    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        """Handle POST request to save or unsave a job.

        Args:
            request: HTTP request object with 'action' parameter.
            job_id (int): ID of the job to save/unsave.

        Returns:
            Response: JSON response with success message.
        """
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
                    {"message": ("Job saved successfully" if created
                                else "Job already saved")},
                    status=(status.HTTP_201_CREATED if created
                            else status.HTTP_200_OK)
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
    """API view to check if a job is saved by the authenticated candidate."""

    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        """Handle GET request to check job save status.

        Args:
            request: HTTP request object.
            job_id (int): ID of the job to check.

        Returns:
            Response: JSON response with save status or error details.
        """
        user = request.user
        try:
            job = Jobs.objects.get(id=job_id)
            candidate = Candidate.objects.get(user=user)
            is_saved = SavedJobs.objects.filter(candidate=candidate,
                                               job=job).exists()
            return Response({"is_saved": is_saved},
                            status=status.HTTP_200_OK)
        except Jobs.DoesNotExist:
            return Response({"error": "Job not found"},
                            status=status.HTTP_404_NOT_FOUND)
        except Candidate.DoesNotExist:
            return Response({"error": "Candidate not found"},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SavedJobsView(APIView):
    """API view to retrieve saved jobs for the authenticated candidate."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Handle GET request to retrieve saved jobs.

        Args:
            request: HTTP request object.

        Returns:
            Response: JSON response with saved job data or error details.
        """
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
    """API view to update the status of a job application."""

    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        """Handle POST request to update application status.

        Args:
            request: HTTP request object with 'action' parameter.
            job_id (int): ID of the applied job.

        Returns:
            Response: JSON response with success message or error details.
        """
        action = request.data.get('action')
        try:
            applied_job = ApplyedJobs.objects.get(id=job_id)
            job_name = applied_job.job.title
            receiver = applied_job.candidate.user

            if applied_job:
                applied_job.status = action
                applied_job.save()

                message = (f"Application status for job {job_name} "
                           f"changed to {action}")
                notifications = Notifications.objects.create(
                    user=receiver, message=message
                )
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
                return Response({"message": "Status changed"},
                                status=status.HTTP_200_OK)
            return Response({"message": "No job available"},
                            status=status.HTTP_204_NO_CONTENT)
        except ApplyedJobs.DoesNotExist:
            return Response({"error": "Job application not found"},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)


class GetQuestions(APIView):
    """API view to retrieve questions for a specific job."""

    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        """Handle GET request to retrieve job questions.

        Args:
            request: HTTP request object.
            job_id (int): ID of the job.

        Returns:
            Response: JSON response with question data or error status.
        """
        try:
            questions = Question.objects.filter(job=job_id)
            serializer = QuestionSerializer(questions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception:
            return Response(status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)



class Applyjob(APIView):
    """API view to handle job application submission by candidates."""

    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        """Handle POST request to apply for a job.

        Args:
            request: HTTP request object with job data and answers.
            job_id (int): ID of the job to apply for.

        Returns:
            Response: JSON response with success message or error details.
        """
        user = request.user
        try:
            job = Jobs.objects.get(id=job_id)
            employer = User.objects.get(id=job.employer.user.id)
            candidate = Candidate.objects.get(user=user)
            if ApplyedJobs.objects.filter(candidate=candidate,
                                          job=job).exists():
                return Response(
                    {'message': 'You have already applied for this job.'},
                    status=status.HTTP_200_OK
                )

            application = ApplyedJobs.objects.create(candidate=candidate,
                                                    job=job)

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
                        question_text=question.text
                    )
                except Question.DoesNotExist:
                    return Response(
                        {'message': f'Question {question_id} not found.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            message = (f"{candidate.user.full_name} is applied for the job "
                       f"you posted {job.title}.")
            notifications = Notifications.objects.create(user=employer,
                                                        message=message)
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
            return Response(
                {'message': 'You have successfully applied for the job.'},
                status=status.HTTP_200_OK
            )
        except Jobs.DoesNotExist:
            return Response({'message': 'Job not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        except Candidate.DoesNotExist:
            return Response({'message': 'Candidate not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)





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




