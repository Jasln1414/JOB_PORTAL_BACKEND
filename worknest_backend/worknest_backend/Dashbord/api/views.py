import calendar
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth, TruncDate
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from django.core.cache import cache
from django.db import DatabaseError
from user_account.models import User
from Empjob.models import Candidate, Employer, Jobs
from payment.models import Payment, EmployerSubscription, SubscriptionPlan

from Empjob.models import  ApplyedJobs
from .serializer import ApplyedJobSerializer


from .serializer import (
    CandidateDetailSerializer, CandidateSerializer,
    EmployerDetailsSerializer, EmployerSerializer,
    AdminJobSerializer, EmployerSubscriptionSerializer,
    SubscriptionPlanSerializer
)

logger = logging.getLogger(__name__)

# ------------------- Employer Management Views -------------------

class EmployerApprovalView(APIView):
    """
    Approve or reject an employer's account.
    Requires admin permissions in production.
    """
    permission_classes = [AllowAny]  

    def post(self, request):
        employer_id = request.data.get('id')
        action = request.data.get('action')  

        try:
            employer = Employer.objects.get(id=employer_id)
            if action == 'approve':
                employer.is_approved_by_admin = True
            elif action == 'reject':
                employer.is_approved_by_admin = False
            else:
                return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)
            
            employer.save()
            return Response({"message": f"Employer {action}ed successfully!"}, status=status.HTTP_200_OK)
        except Employer.DoesNotExist:
            return Response({"error": "Employer not found"}, status=status.HTTP_404_NOT_FOUND)

class StatusView(APIView):
    """
    Block or unblock a candidate or employer account.
    Requires admin authentication.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        id = request.data.get('id')
        action = request.data.get('action')
        entity_type = request.data.get('type')

        if not all([id, action, entity_type]):
            return Response({"error": "Missing required fields: id, action, or type"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if entity_type == "candidate":
                candidate = Candidate.objects.get(id=id)
                user = User.objects.get(id=candidate.user.id)
                entity_name = f"Candidate {id}"
            elif entity_type == "employer":
                employer = Employer.objects.get(id=id)
                user = User.objects.get(id=employer.user.id)
                entity_name = f"Employer {id}"
            else:
                return Response({"error": "Invalid type. Use 'candidate' or 'employer'"}, status=status.HTTP_400_BAD_REQUEST)

            if action == 'block':
                user.is_active = False
                user.save()
                logger.info(f"{entity_name} blocked by {request.user}")
            elif action == 'unblock':
                user.is_active = True
                user.save()
                logger.info(f"{entity_name} unblocked by {request.user}")
            else:
                return Response({"error": "Invalid action. Use 'block' or 'unblock'"}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"message": f"{entity_name} status changed successfully"}, status=status.HTTP_200_OK)

        except Candidate.DoesNotExist:
            return Response({"error": f"Candidate with id {id} not found"}, status=status.HTTP_404_NOT_FOUND)
        except Employer.DoesNotExist:
            return Response({"error": f"Employer with id {id} not found"}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({"error": "Associated user not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error in StatusView: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ------------------- Dashboard and Statistics Views -------------------

class HomeView(APIView):
    """
    Retrieve counts of candidates, employers, and active jobs for the dashboard.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        candidates_count = Candidate.objects.count()
        employers_count = Employer.objects.count()
        jobs_count = Jobs.objects.filter(active=True).count()
        
        data = {
            'candidates_count': candidates_count,
            'employers_count': employers_count,
            'jobs_count': jobs_count,
        }
        return Response(data, status=status.HTTP_200_OK)




# ------------------- Candidate and Employer Listing Views -------------------

class CandidateListView(APIView):
    """
    Retrieve a list of all candidates.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        logger.info("Fetching all candidates...")
        candidates = Candidate.objects.all()
        serializer = CandidateSerializer(candidates, many=True)
        logger.debug(f"Serialized candidates: {serializer.data}")
        return Response(serializer.data, status=status.HTTP_200_OK)

class EmployerListView(APIView):
    """
    Retrieve a list of all employers.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        logger.info("Fetching all employers...")
        employers = Employer.objects.all()
        serializer = EmployerSerializer(employers, many=True)
        logger.debug(f"Serialized employers: {serializer.data}")
        return Response(serializer.data, status=status.HTTP_200_OK)

class CandidateView(APIView):
    """
    Retrieve details of a specific candidate by ID.
    """
    permission_classes = [AllowAny]

    def get(self, request, id):
        logger.info(f"Fetching candidate with id {id}...")
        try:
            candidate = Candidate.objects.get(id=id)
            serializer = CandidateDetailSerializer(candidate)
            logger.debug(f"Serialized candidate: {serializer.data}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            logger.error(f"Candidate with id {id} not found")
            return Response({"error": "Candidate not found"}, status=status.HTTP_404_NOT_FOUND)
        










class CandidateAppliedJobsView(APIView):
    """
    Retrieve all applied jobs for a specific candidate by ID.
    Restricted to admin users.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, id):
        try:
            candidate = Candidate.objects.get(id=id)
            applied_jobs = ApplyedJobs.objects.filter(candidate=candidate)
            serializer = ApplyedJobSerializer(applied_jobs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            return Response({"error": "Candidate not found"}, status=status.HTTP_404_NOT_FOUND)

class EmployerView(APIView):
    """
    Retrieve details of a specific employer by ID.
    """
    permission_classes = [AllowAny]

    def get(self, request, id):
        logger.info(f"Fetching employer with id {id}...")
        try:
            employer = Employer.objects.get(id=id)
            serializer = EmployerDetailsSerializer(employer)
            logger.debug(f"Serialized employer: {serializer.data}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Employer.DoesNotExist:
            logger.error(f"Employer with id {id} not found")
            return Response({"error": "Employer not found"}, status=status.HTTP_404_NOT_FOUND)

# ------------------- Job Management Views -------------------

class AdminGetAllJobs(APIView):
    """
    Retrieve a list of all jobs, with optional filtering by active status.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            jobs = Jobs.objects.all()
            active_status = request.query_params.get('active')
            if active_status is not None:
                active_status = active_status.lower() == 'true'
                jobs = jobs.filter(active=active_status)
                
            serializer = AdminJobSerializer(jobs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching jobs: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminGetJobDetail(APIView):
    """
    Retrieve details of a specific job by ID.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            job = Jobs.objects.get(pk=pk)
            serializer = AdminJobSerializer(job)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Jobs.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error fetching job {pk}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminJobModeration(APIView):
    """
    Moderate a job by activating, deactivating, or deleting it.
    """
    permission_classes = [AllowAny]

    def post(self, request, job_id):
        action = request.data.get('action')
        reason = request.data.get('reason', '')

        if action not in ['deactivate', 'activate', 'delete']:
            return Response({"error": "Invalid action. Use 'activate', 'deactivate', or 'delete'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            job = Jobs.objects.get(id=job_id)
            if action == 'deactivate':
                job.active = False
                job.moderation_note = reason
                job.save()
                message = "Job deactivated successfully"
            elif action == 'activate':
                job.active = True
                job.moderation_note = reason
                job.save()
                message = "Job activated successfully"
            elif action == 'delete':
                job.delete()
                message = "Job deleted successfully"

                if action != 'delete':
                    serializer = AdminJobSerializer(job)
                    return Response({"message": message, "job": serializer.data}, status=status.HTTP_200_OK)
            return Response({"message": message}, status=status.HTTP_200_OK)

        except Jobs.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error moderating job {job_id}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApplicationStatsView(APIView):
    """
    Retrieve the top 10 jobs by application count.
    Requires admin authentication.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        application_stats = Jobs.objects.annotate(
            application_count=Count('jobapplication')
        ).filter(
            application_count__gt=0
        ).values(
            'id', 'title', 'application_count', 'company_name'
        ).order_by('-application_count')[:10]

        result = [{
            'job_id': item['id'],
            'job_title': item['title'],
            'company_name': item['company_name'],
            'application_count': item['application_count']
        } for item in application_stats]

        return Response(result, status=status.HTTP_200_OK)

# ------------------- Subscription and Sales Views -------------------

class SalesReportView(APIView):
    """
    Retrieve sales data including total revenue, subscribers, and active subscriptions.
    Requires admin authentication.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            sales = EmployerSubscription.objects.all()
            payments = Payment.objects.filter(status='success')
            active_subscribers = EmployerSubscription.objects.filter(status='active')
            subscription_plans = SubscriptionPlan.objects.all()

            total_revenue = sum(payment.amount for payment in payments)
            total_subscribers = sales.count()

            data = {
                'total_revenue': total_revenue,
                'total_subscribers': total_subscribers,
                'total_plans': subscription_plans.count(),
                'activeSubscribers': active_subscribers.count(),
                'sales': EmployerSubscriptionSerializer(sales, many=True).data,
            }
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in SalesReportView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SubscriptionGrowthReportView(APIView):
    """
    Retrieve monthly subscription growth data for a specified year.
    Requires admin authentication.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            year = request.query_params.get('year')
            if not year:
                return Response({"error": "Year is required"}, status=status.HTTP_400_BAD_REQUEST)

            subscriptions = EmployerSubscription.objects.filter(
                start_date__year=year,
                status='active'
            ).annotate(month=ExtractMonth('start_date'))

            result = {}
            for month_num in range(1, 13):
                month_subs = subscriptions.filter(month=month_num)
                no_employers = month_subs.count()
                payments = month_subs.aggregate(total_payments=Sum('payment__amount'))['total_payments'] or 0

                result[calendar.month_name[month_num].lower()] = {
                    'no_employers': no_employers,
                    'payments': payments
                }

            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in SubscriptionGrowthReportView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SubscriptionPlanUpdateView(APIView):
    """
    Update a subscription plan by ID.
    Requires admin authentication.
    """
    permission_classes = [IsAdminUser]

    def put(self, request, pk):
        logger.debug(f"Received PUT request for plan pk={pk}, data={request.data}")
        try:
            plan = SubscriptionPlan.objects.get(pk=pk)
            serializer = SubscriptionPlanSerializer(plan, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                logger.debug(f"Plan pk={pk} updated successfully")
                return Response(serializer.data, status=status.HTTP_200_OK)
            logger.error(f"Invalid data for pk={pk}: {serializer.errors}")
            return Response({"error": "Invalid data provided", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except SubscriptionPlan.DoesNotExist:
            logger.warning(f"Plan with pk={pk} not found")
            return Response({"error": "Subscription plan not found"}, status=status.HTTP_404_NOT_FOUND)

class SubscriptionPlanListView(APIView):
    """
    Retrieve a list of all subscription plans.
    Requires admin authentication.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        plans = SubscriptionPlan.objects.all()
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)





class SubscriptionPlanDeleteView(APIView):
    """
    Delete a subscription plan by ID.
    Requires admin authentication.
    """
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        try:
            plan = SubscriptionPlan.objects.get(pk=pk)
            # Check for active subscriptions using status field
            active_subscriptions = EmployerSubscription.objects.filter(plan=plan, status='active').count()
            if active_subscriptions > 0:
                logger.warning(f"Cannot delete plan pk={pk} due to {active_subscriptions} active subscriptions")
                return Response(
                    {"error": f"Cannot delete plan with {active_subscriptions} active subscriptions"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            plan.delete()
            logger.debug(f"Plan pk={pk} deleted successfully")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except SubscriptionPlan.DoesNotExist:
            logger.warning(f"Plan with pk={pk} not found")
            return Response({"error": "Subscription plan not found"}, status=status.HTTP_404_NOT_FOUND)