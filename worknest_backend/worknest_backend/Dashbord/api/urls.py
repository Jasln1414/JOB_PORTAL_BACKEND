from django.urls import path

from .views import (
    HomeView, CandidateView, EmployerView, CandidateListView, EmployerListView,
    EmployerApprovalView, StatusView, AdminGetAllJobs, AdminGetJobDetail,
    AdminJobModeration,
    ApplicationStatsView, SalesReportView, SubscriptionGrowthReportView,
    SubscriptionPlanListView, SubscriptionPlanUpdateView, SubscriptionPlanDeleteView,CandidateAppliedJobsView
)

# URL patterns for the application
urlpatterns = [
    # ------------------- Dashboard and Home -------------------
    path('home/', HomeView.as_view(), name='home'),

    # ------------------- Candidate Management -------------------
    path('clist/', CandidateListView.as_view(), name='candidatelist'),
    path('candidate/<int:id>/', CandidateView.as_view(), name='candidate-detail'),
    # path('getApplyedjobs/', GetApplyedjob.as_view(), name="getapplyedjob"),
    path('admin/candidate/<int:id>/applied-jobs/', CandidateAppliedJobsView.as_view(), name='candidate-applied-jobs'),
    
    # ------------------- Employer Management -------------------
    path('elist/', EmployerListView.as_view(), name='employerlist'),
    path('employer/<int:id>/', EmployerView.as_view(), name='employer'),
    path('api/employer/approval/', EmployerApprovalView.as_view(), name='employer-approval'),
    path('status/', StatusView.as_view(), name='status'),

    # ------------------- Job Management -------------------
    path('admin/jobs/', AdminGetAllJobs.as_view(), name='admin-get-all-jobs'),
    path('admin/job/<int:pk>/', AdminGetJobDetail.as_view(), name='admin-get-job-detail'),
    path('admin/jobs/<int:job_id>/moderate/', AdminJobModeration.as_view(), name='admin-job-moderation'),

    
    
    path('reports/application-stats/', ApplicationStatsView.as_view(), name='application-stats'),
    path('salesReport/', SalesReportView.as_view(), name='sales-report'),
    path('subscription-growth/', SubscriptionGrowthReportView.as_view(), name='subscription-growth-report'),

    # ------------------- Subscription Plans -------------------
    path('subscription/plans/', SubscriptionPlanListView.as_view(), name='list-subscription-plans'),
    path('subscription/plans/<int:pk>/', SubscriptionPlanUpdateView.as_view(), name='update-subscription-plan'),
    path('subscription/plans/<int:pk>/delete/', SubscriptionPlanDeleteView.as_view(), name='delete-subscription-plan'),
]