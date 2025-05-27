# Empjob/api/urls.py
from django.urls import path

#from payment.views import RenewSubscription
from .views import  SavedJobsView, SavejobStatus, CheckJobSaveStatus
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Job related endpoints
    path('postjob/', views.PostJob.as_view(), name="postjob"),
    path('editJob/', views.EditJob.as_view(), name="Editjob"),
    path('getjobs/', views.GetJob.as_view(), name="getjobs"),
    path('getAlljobs/', views.GetAllJob.as_view(), name="getAlljobs"),
    path('getjobs/detail/<int:job_id>/', views.GetJobDetail.as_view(), name="getjob_detail"),
    path('getApproval/<int:candidate_id>/<int:employer_id>/', views.GetApproveView.as_view(), name="getApproval"),
    path('approveChat/<int:approvalId>/', views.ChatApprovalView.as_view(), name="approve-chat"),
    
    # Profile endpoints
    path('profile/', views.ProfileView.as_view(), name="profile"),
    
    # Application endpoints
    path('applyjob/<int:job_id>/', views.Applyjob.as_view(), name="applyjob"),
    path('getApplyedjobs/', views.GetApplyedjob.as_view(), name="getapplyedjob"),
    path('getApplicationjobs/', views.GetApplicationjob.as_view(), name="getApplicationjob"),
    
    # Question endpoints
    path('getjobs/questions/<int:job_id>/', views.GetQuestions.as_view(), name="getjob_questions"),
    
    # Status endpoints
    path('getjobs/status/<int:job_id>/', views.GetJobStatus.as_view(), name="job-status"),
    path('applicationStatus/<int:job_id>/', views.ApplicationStatusView.as_view(), name='applicationStatus'),
    
    # Saved jobs endpoints
    path('savejob/<int:job_id>/', SavejobStatus.as_view(), name='save-job'),  # Changed to match frontend
    path('check-saved/<int:job_id>/', CheckJobSaveStatus.as_view(), name='check-saved'),  # Already correct
    path('savedjobs/', SavedJobsView.as_view(), name='saved-jobs'),  # Changed to match frontend
    



    path('search/', views.JobSearchView.as_view(), name='job-search'),
    path('autocomplete/', views.JobAutocompleteView.as_view(), name='job-autocomplete'),
   
    
    # Utility endpoints
    path('api/get-csrf-token/', views.get_csrf_token, name='get-csrf-token'),
    path('check-application/<int:job_id>/', views.check_application, name='check_application'),

    path('job-usage/', views.JobUsageView.as_view(), name='job-usage'),
   
    # path('subscription/renew/', RenewSubscription.as_view(), name='create-subscription'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    
