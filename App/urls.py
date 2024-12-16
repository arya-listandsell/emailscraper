from django.urls import path
from App import views

urlpatterns = [
    path('', views.form_request,name='form_request'),
    path('get_branches/', views.branch_name_autocomplete, name='get_branches'),
    path('fetch_emails/', views.fetch_emails, name='fetch_emails'),
    
    
]