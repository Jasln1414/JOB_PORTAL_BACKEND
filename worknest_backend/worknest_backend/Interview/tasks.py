from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task(bind=True)
def send_shedule_mail(self, email, date, username, title):
    try:
        subject = "Interview Schedule Notification"
        email_from = settings.EMAIL_HOST_USER
        message = (
            f"Dear Candidate,\n\n"
            f"This email is to inform you about your upcoming interview.\n\n"
            f"Company: {username}\n"
            f"Job Title: {title}\n"
            f"Date & Time: {date}\n\n"
            f"Please ensure you are available for the interview at the scheduled time.\n\n"
            f"Best regards,\n"
            f"{username}"
        )
        print("Email details:")
        print(f"From: {email_from}")
        print(f"To: {email}")
        print(f"Subject: {subject}")
        print("Message:")
        print(message)

        send_mail(subject, message, email_from, [email], fail_silently=False)
        print(f"Email sent successfully to {email}")
        return {"status": "success", "email": email}
    except Exception as e:
        print(f"Error sending email: {e}")
        raise self.retry(countdown=60, max_retries=3)

@shared_task(bind=True)
def cancell_shedule_mail(self, email, date, username, title):
    try:
        subject = "Application Status Update"
        email_from = settings.EMAIL_HOST_USER
        message = (
            f"Dear Candidate,\n\n"
            f"We regret to inform you that your application for {title} at {username} "
            f"has been rejected.\n\n"
            f"Thank you for your interest.\n\n"
            f"Best regards,\n"
            f"{username}"
        )
        print("Email details:")
        print(f"From: {email_from}")
        print(f"To: {email}")
        print(f"Subject: {subject}")
        print("Message:")
        print(message)

        send_mail(subject, message, email_from, [email], fail_silently=False)
        print(f"Email sent successfully to {email}")
        return {"status": "success", "email": email}
    except Exception as e:
        print(f"Error sending email: {e}")
        raise self.retry(countdown=60, max_retries=3)

@shared_task(bind=True)
def send_acceptance_mail(self, email, username, title):
    try:
        subject = "Job Application Accepted"
        email_from = settings.EMAIL_HOST_USER
        message = (
            f"Dear Candidate,\n\n"
            f"Congratulations! Your application for {title} at {username} has been accepted.\n\n"
            f"We will contact you soon with next steps.\n\n"
            f"Best regards,\n"
            f"{username}"
        )
        print("Email details:")
        print(f"From: {email_from}")
        print(f"To: {email}")
        print(f"Subject: {subject}")
        print("Message:")
        print(message)

        send_mail(subject, message, email_from, [email], fail_silently=False)
        print(f"Email sent successfully to {email}")
        return {"status": "success", "email": email}
    except Exception as e:
        print(f"Error sending email: {e}")
        raise self.retry(countdown=60, max_retries=3)
    
# @shared_task(bind=True)
# def test(self):
#     for i in range(10):
#         print(i)
#     return 'done'
from celery import shared_task

@shared_task
def send_welcome_email(user_id):
    # Simulate sending an email
    print(f"Sending email to user {user_id}")
 # interview/tasks.py
from celery import shared_task

@shared_task
def sample_interview_task():
    print("Running interview task!")
    return "Task completed"   