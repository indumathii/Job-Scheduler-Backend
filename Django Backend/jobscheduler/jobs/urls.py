from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import JobViewset,RegisterView,LoginView,UserJobsView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

router=DefaultRouter()
router.register(r'jobs',JobViewset)

urlpatterns=[path('',include(router.urls)),
            path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
            path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
            path('register/',RegisterView.as_view(),name='user-register'),
            path('login/', LoginView.as_view(), name='user-login'),
            path('joblist/<int:user_id>/', UserJobsView.as_view(), name='job-list'),
            #path('api/jobs/dashboard/<str:status>/', JobListView.as_view(), name='jobs-dashboard'),
            ]
