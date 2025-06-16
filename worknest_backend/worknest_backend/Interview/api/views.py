from datetime import datetime, timedelta
from modulefinder import test
from django.utils import timezone
import urllib.parse
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializer import SheduleInterviewSerializer, InterviewSheduleSerializer
from user_account.models import Employer, Candidate, User
from Interview.models import InterviewShedule
from Empjob.models import Jobs, ApplyedJobs
from chat.models import Notifications
from rest_framework.permissions import IsAuthenticated, AllowAny
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from Interview.tasks import send_shedule_mail, cancell_shedule_mail
import logging

logger = logging.getLogger(__name__)


class InterviewSheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info("Scheduling interview")
        user = request.user
        try:
            employer = Employer.objects.get(user=user)
            candidate_id = request.data.get('candidate')
            job_id = request.data.get('job')
            application_id = request.data.get('application_id')
            date = request.data.get('date')
            candidate = Candidate.objects.get(id=candidate_id)
            job = Jobs.objects.get(id=job_id)
            applyed_job = ApplyedJobs.objects.get(id=application_id, candidate=candidate, job=job)
            email = candidate.user.email
            title = job.title
            username = employer.user.full_name
            logger.info(f"Scheduling interview: email={email}, date={date}, username={username}, title={title}")
        except Candidate.DoesNotExist:
            logger.error("Candidate not found")
            return Response({"message": "Candidate not found"}, status=status.HTTP_404_NOT_FOUND)
        except Jobs.DoesNotExist:
            logger.error("Job not found")
            return Response({"message": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
        except Employer.DoesNotExist:
            logger.error("Employer not found")
            return Response({"message": "Employer not found"}, status=status.HTTP_404_NOT_FOUND)
        except ApplyedJobs.DoesNotExist:
            logger.error("Application not found")
            return Response({"message": "Application not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = SheduleInterviewSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            interview = serializer.save()
            logger.info(f"Interview created: {interview.id}")

            # Update AppliedJobs status
            applyed_job.status = "Interview Scheduled"
            applyed_job.save()

            send_shedule_mail.delay(email, date, username, title)
            message = f"Interview scheduled for {title} on {date}"
            Notifications.objects.create(user=candidate.user, message=message)
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notification_{candidate.user.id}',
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
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.error(f"Serializer errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class getShedulesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        logger.info(f"getShedulesView: User {user}")
       
        try:
            try:
                candidate = Candidate.objects.get(user=user)
                schedules = InterviewShedule.objects.filter(candidate=candidate, active=True)
            except Candidate.DoesNotExist:
                employer = Employer.objects.get(user=user)
                schedules = InterviewShedule.objects.filter(employer=employer, active=True)

            logger.info(f"Fetched {schedules.count()} active schedules for user {user}")
            serializer = InterviewSheduleSerializer(schedules, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except (Candidate.DoesNotExist, Employer.DoesNotExist):
            return Response({"message": "User is neither a candidate nor an employer"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error: {e}")
            return Response({"message": f"Failed to fetch schedules: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InterviewStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, interview_id):
        action = request.data.get('action')
        print("actionnnnnnnnnnnnnnnnnnnnnnnnn",action)
        user=request.user
        
        logger.info(f"InterviewStatusView: Processing POST request for interview ID {interview_id} with action {action}")
        try:
            is_candidate = Candidate.objects.filter(user_id=user.id).exists()
           
            is_employer = Employer.objects.filter(user_id=user.id).exists()
            interview = InterviewShedule.objects.get(id=interview_id)
            job = Jobs.objects.get(id=interview.job_id)
            candidate = Candidate.objects.get(id=interview.candidate_id)
            applyedjobs = ApplyedJobs.objects.get(candidate=candidate, job=job)
            logger.info(f"Interview: {interview}, Job: {job}, Candidate: {candidate}, AppliedJobs: {applyedjobs}")
        except (Jobs.DoesNotExist, Candidate.DoesNotExist, InterviewShedule.DoesNotExist, ApplyedJobs.DoesNotExist) as e:
            logger.error(f"Required data not found: {str(e)}")
            return Response({"message": "Something went wrong"}, status=status.HTTP_404_NOT_FOUND)

        if action == 'Accepted':
            interview.status = 'Accepted'
            message = f"Congratulations! You have been selected for the job {job.title}."
            applyedjobs.status = 'Accepted'
        elif action == 'Rejected':
            interview.status = 'Rejected'
            message = f"Sorry, you have been rejected for the job {job.title}."
            applyedjobs.status = 'Rejected'
        elif action == 'Completed' and is_candidate:
            interview.status = 'Completed'
            message = f"Great job completing your interview for the '{job.title}' position! We encourage you to follow up with the employer regarding the next steps."

                    
        elif action == 'Missed':
            interview.selected =True
            interview.status = 'You missed'
            message = f"You missed your interview for the job '{job.title}'. Please contact the employer for further steps."


        else:
            logger.error(f"Invalid action: {action}")
            return Response({"message": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)

        # interview.active = False  # Prevent Celery task from processing
        interview.save()
        applyedjobs.save()

        Notifications.objects.create(user=candidate.user, message=message)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notification_{candidate.user.id}',
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
        logger.info(f"Interview {interview_id} updated to {action}, notification sent to candidate {candidate.user.id}")

        return Response({"message": "Status changed"}, status=status.HTTP_200_OK)
    

from celery import shared_task # type: ignore

class CancelApplicationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        try:
            employer = Employer.objects.get(user=user)
        except Employer.DoesNotExist:
            return Response({"message": "Employer not found"}, status=status.HTTP_404_NOT_FOUND)

        candidate_id = request.data.get('candidate_id')
        job_id = request.data.get('job_id')

        try:
            job = Jobs.objects.get(id=job_id)
            candidate = Candidate.objects.get(id=candidate_id)
            
            # Get the latest active interview
            latest_interview = InterviewShedule.objects.filter(
                job=job_id,
                candidate=candidate_id,
                active=True
            ).order_by('-date').first()

            if not latest_interview:
                return Response({"message": "No active interview found"}, status=status.HTTP_404_NOT_FOUND)

            # Prevent cancellation if interview was attended or in final state
            if latest_interview.attended:
                return Response(
                    {"message": "Cannot cancel interview. The interview has already been attended."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if latest_interview.status in ['Completed', 'Selected', 'Rejected', 'Accepted']:
                return Response(
                    {"message": f"Cannot cancel interview. Interview status is {latest_interview.status}."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update the application status
            try:
                applied_job = ApplyedJobs.objects.get(candidate=candidate_id, job=job_id)
                applied_job.status = 'Interview Cancelled'
                applied_job.save()
            except ApplyedJobs.DoesNotExist:
                logger.error(f"No application found for candidate {candidate_id} and job {job_id}")
                return Response(
                    {"message": "No application found for this candidate and job"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Mark interview as cancelled
            latest_interview.active = False
            latest_interview.status = "Canceled"
            latest_interview.save()

            # Prepare notification data
            notification_data = {
                'user': candidate.user,
                'message': f'Interview for {job.title} scheduled on {latest_interview.date} has been cancelled.',
                'is_read': False,
                'created_at': timezone.now()
            }

            # Create notification
            try:
                notification = Notifications.objects.create(**notification_data)
                
                # Send via channel layer
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'notification_{candidate.user.id}',
                    {
                        'type': 'notify_message',
                        'message': {
                            'id': notification.id,
                            'text': notification.message,
                            'sender': "employer",
                            'is_read': False,
                            'timestamp': notification.created_at.isoformat(),
                            'chat_id': None
                        },
                        'unread_count': Notifications.objects.filter(
                            user=candidate.user, 
                            is_read=False
                        ).count()
                    }
                )
                logger.info(f"Notification sent to candidate {candidate.user.id}")
            except Exception as e:
                logger.error(f"Failed to send notification: {str(e)}")
                return Response(
                    {"message": "Interview cancelled but failed to send notification"},
                    status=status.HTTP_206_PARTIAL_CONTENT
                )

            # Send cancellation email
            try:
                cancell_shedule_mail.delay(
                    candidate.user.email,
                    str(latest_interview.date),
                    employer.user.full_name,
                    job.title
                )
                logger.info("Cancellation email queued successfully")
            except Exception as e:
                logger.error(f"Failed to queue cancellation email: {str(e)}")

            return Response(
                {"message": "Interview cancelled successfully"},
                status=status.HTTP_200_OK
            )

        except (Jobs.DoesNotExist, Candidate.DoesNotExist) as e:
            logger.error(f"Error: {str(e)}")
            return Response(
                {"message": "Candidate or Job not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return Response(
                {"message": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
################ INTERVIEW JOIN STATUS TRACKING



class InterviewJoinStatus(APIView):
    permission_classes=[IsAuthenticated]

    def post(self,request,interview_id):
        print("ineterviewidddddddddddddddddddd",interview_id)

        user=request.user
        try:
            interview=InterviewShedule.objects.get(id=interview_id)
            print("ineterviewidddddddddddddddddddd",interview)

            is_candidate = Candidate.objects.filter(user_id=user.id).exists()
            print("candiidddddddddddddddddddd",is_candidate)
            is_employer = Employer.objects.filter(user_id=user.id).exists()
            print("empewidddddddddddddddddddd",is_employer)
            if is_candidate:
                interview.attended=True
                interview.save()
                return Response({"message:candidate Interview attended"},status=status.HTTP_200_OK)
            if is_employer:
                pass
                return Response({"blaaaaaaa"})
        except InterviewShedule.DoesNotExist:
            return Response({"message:Interview doesnt exists"},status=status.HTTP_400_BAD_REQUEST)

class InterviewLinkSend(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, interview_id):
        try:
            link = request.data.get("link")
            message = f'Join your interview: <a href="{link}" target="_blank" style="color:blue;">Click here</a>'
            if not link:
                return Response(
                    {"message": "A link is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            parsed_url = urllib.parse.urlparse(link)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                return Response(
                    {"message": "Invalid URL provided"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            interview = InterviewShedule.objects.get(id=interview_id)
            candidate = Candidate.objects.get(id=interview.candidate_id)
            

           
            notification = Notifications.objects.create(
            user=candidate.user,
            message=f"Join your interview: {link}",  
        )

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notification_{candidate.user.id}',
                {
                    'type': 'notify_message',
                    'message': {
                        'id': notification.id,
                        'text': notification.message,
                        'sender': "employer",
                        'is_read': False,
                        'timestamp': datetime.now().isoformat(),
                        'link': link
                    },
                    'unread_count': Notifications.objects.filter(user=candidate.user, is_read=False).count()
                }
            )

            return Response(
                {"message": "Interview link sent successfully", "notification_id": notification.id},
                status=status.HTTP_200_OK
            )

        except InterviewShedule.DoesNotExist:
            return Response(
                {"message": "Interview not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Candidate.DoesNotExist:
            return Response(
                {"message": "Candidate not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return Response(
                {"message": f"Something went wrong: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

def testView(request):
    test.delay()
    return HttpResponse("Done")