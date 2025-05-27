from modulefinder import test
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializer import SheduleInterviewSerializer,  InterviewSheduleSerializer
from user_account.models import Employer, Candidate, User
from Interview.models import InterviewShedule
from Empjob.models import Jobs, ApplyedJobs
from chat.models import Notifications
from rest_framework.permissions import IsAuthenticated, AllowAny
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from Interview.tasks import send_shedule_mail, cancell_shedule_mail
from datetime import datetime, timedelta
from django.utils import timezone
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

            # Update ApplyedJobs status
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
            applications = InterviewShedule.objects.filter(
                job=job_id,
                candidate=candidate_id,
                active=True
            )
            if not applications.exists():
                return Response({"message": "No active interview found"}, status=status.HTTP_404_NOT_FOUND)

            # Get the latest interview
            latest_interview = applications.order_by('-date').first()
            email = candidate.user.email
            username = employer.user.full_name
            date = latest_interview.date
            title = job.title

            # Prevent cancellation if interview was attended
            if latest_interview.attended:
                return Response(
                    {"message": "Cannot cancel interview. The interview has already been attended."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Prevent cancellation if interview is completed, selected, or rejected
            if latest_interview.status in ['Completed', 'Selected', 'Rejected']:
                return Response(
                    {"message": f"Cannot cancel interview. Interview status is {latest_interview.status}."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # # Prevent cancellation if interview is within 24 hours
            # now = timezone.now()
            # time_until_interview = date - now
            # if time_until_interview < timedelta(hours=24):
            #     return Response(
            #         {"message": "Cannot cancel interview within 24 hours of the scheduled time."},
            #         status=status.HTTP_400_BAD_REQUEST
            #     )

            # Update the application status
            try:
                applyed = ApplyedJobs.objects.get(candidate=candidate_id, job=job_id)
                applyed.status = 'Interview Cancelled'
                applyed.save()
            except ApplyedJobs.DoesNotExist:
                logger.warning("No application found for this candidate and job")
                pass

            # Mark interview as cancelled
            applications.update(active=False, status="Canceled")

            # Send notification
            message = f'Interview for {job.title} has been cancelled.'
            Notifications.objects.create(user=candidate.user, message=message)
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notification_{candidate_id}',
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

            # Send cancellation email
            try:
                if date:
                    cancell_shedule_mail.delay(email, date, username, title)
                    logger.info("Cancel email task queued successfully")
            except Exception as e:
                logger.warning(f"Failed to queue cancel email task: {e}")

            return Response({"message": "Interview cancelled successfully"}, status=status.HTTP_200_OK)

        except (Jobs.DoesNotExist, Candidate.DoesNotExist) as e:
            logger.error(f"Error: {str(e)}")
            return Response({"message": "Candidate or Job not found"}, status=status.HTTP_404_NOT_FOUND)





class getShedulesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        logger.info(f"getShedulesView: User {user}")
        try:
            try:
                candidate = Candidate.objects.get(user=user)
                schedules = InterviewShedule.objects.filter(candidate=candidate)
            except Candidate.DoesNotExist:
                employer = Employer.objects.get(user=user)
                schedules = InterviewShedule.objects.filter(employer=employer)

            serializer = InterviewSheduleSerializer(schedules, many=True)  
            return Response(serializer.data, status=status.HTTP_200_OK)
        except (Candidate.DoesNotExist, Employer.DoesNotExist):
            return Response({"message": "User is neither a candidate nor an employer"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error: {e}")
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
class InterviewView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        logger.info(f"InterviewView: Processing POST request, data={request.data}")
        roomId = request.data.get("roomId")
        interviewId = request.data.get("interviewId")
        try:
            interview = InterviewShedule.objects.get(id=interviewId)
            now = timezone.now()
            window_end = interview.date + timedelta(minutes=15)
            
            interview.attended = True
            if now > window_end and interview.status == 'Upcoming':
                interview.status = 'Completed'
                interview.active = False
            interview.save()
            logger.info(f"Updated interview {interviewId}: attended={interview.attended}, status={interview.status}")
            
            candidate_id = interview.candidate.user.id
            message = f'Interview call started - {roomId} - {interviewId}'
            Notifications.objects.create(user=interview.candidate.user, message=message)
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notification_{candidate_id}',
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
            logger.info(f"Sent notification to notification_{candidate_id}")
            return Response({"message": "Notification sent"}, status=status.HTTP_200_OK)
        except InterviewShedule.DoesNotExist:
            logger.error(f"Interview {interviewId} not found")
            return Response({"message": "No interview data found"}, status=status.HTTP_404_NOT_FOUND)

class InterviewSheduleStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    def patch(self, request, interview_id):
        try:
            interview = InterviewShedule.objects.get(id=interview_id)
            new_status = request.data.get('status')
            attended = request.data.get('attended')
            if new_status and new_status not in dict(InterviewShedule.STATUS_CHOICES):
                logger.error(f"Invalid status: {new_status}")
                return Response({"message": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
            
            if new_status:
                interview.status = new_status
            if attended is not None:
                interview.attended = attended
            if new_status == 'You missed':
                interview.active = False
            elif new_status == 'Completed':
                interview.attended = True
                interview.active = False
            interview.save()
            logger.info(f"Updated interview {interview.id}: status={new_status}, attended={attended}")

            candidate_id = interview.candidate.user.id
            message = f"Interview status for {interview.job.title} updated to {interview.status}."
            Notifications.objects.create(user=interview.candidate.user, message=message)
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notification_{candidate_id}',
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
            return Response({"message": "Status updated successfully"}, status=status.HTTP_200_OK)
        except InterviewShedule.DoesNotExist:
            logger.error(f"Interview {interview_id} not found")
            return Response({"message": "Interview not found"}, status=status.HTTP_404_NOT_FOUND)




class InterviewStatusView(APIView):
    permission_classes = [IsAuthenticated]  # Changed to IsAuthenticated for security
    def post(self, request, interview_id):
        action = request.data.get('action')
        logger.info(f"InterviewStatusView: Processing POST request for interview ID {interview_id} with action {action}")
        try:
            interview = InterviewShedule.objects.get(id=interview_id)
            job = Jobs.objects.get(id=interview.job_id)
            candidate = Candidate.objects.get(id=interview.candidate_id)
            applyedjobs = ApplyedJobs.objects.get(candidate=candidate, job=job)
            logger.info(f"Interview: {interview}, Job: {job}, Candidate: {candidate}, ApplyedJobs: {applyedjobs}")
        except (Jobs.DoesNotExist, Candidate.DoesNotExist, InterviewShedule.DoesNotExist, ApplyedJobs.DoesNotExist):
            logger.error("Required data not found")
            return Response({"message": "Something went wrong"}, status=status.HTTP_404_NOT_FOUND)

        if action == 'Accepted':
            interview.status = 'Selected'
            interview.selected = True
            message = f"Congratulations! You have been selected for the interview for the job {job.title}."
            applyedjobs.status = 'Accepted'
        elif action == 'Rejected':
            interview.status = 'Rejected'
            interview.selected = True
            message = f"Sorry, you have been rejected for the interview for the job {job.title}."
            applyedjobs.status = 'Rejected'
        else:
            return Response({"message": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)

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

        return Response({"message": "Status changed"}, status=status.HTTP_200_OK)

def testView(request):
    test.delay()
    return HttpResponse("Done")