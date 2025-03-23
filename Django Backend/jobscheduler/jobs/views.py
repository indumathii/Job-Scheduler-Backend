from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from asgiref.sync import sync_to_async
from concurrent.futures import ThreadPoolExecutor
from django.db.models import Case, When, Value, IntegerField
from django.db import transaction
import logging
import queue
import threading

from .models import Job
from .serializers import JobSerializer, RegisterSerializer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PRIORITY_MAP = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
MAX_CONCURRENT_JOBS = 3

# Thread-safe job manager
class JobManager:
    def __init__(self, max_workers=MAX_CONCURRENT_JOBS):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.priority_queue = queue.PriorityQueue()
        self.lock = threading.Lock()  # For thread-safe operations
        self.active_jobs = 0  # Track running jobs

    def submit_job(self, job):
        """Submit a job for execution."""
        with self.lock:
            if self.active_jobs < self.executor._max_workers:
                self.active_jobs += 1
                self.executor.submit(self.execute_job, job)
            else:
                priority = PRIORITY_MAP.get(job.priority, 0)
                self.priority_queue.put((-priority, job.deadline, job.id, job))

    def execute_job(self, job):
        """Execute a job and manage its lifecycle."""
        try:
            with transaction.atomic():  # Ensure DB consistency
                job.start_time = timezone.now()
                job.status = Job.Status.RUNNING
                job.save(update_fields=['start_time', 'status'])
            logger.info(f"Started job: {job.job_name} (Priority: {job.priority})")

            # Simulate execution (replace with AI logic later)
            time.sleep(job.estimated_duration / 60)  # Assuming minutes

            with transaction.atomic():
                job.end_time = timezone.now()
                job.status = Job.Status.COMPLETED
                job.execution_time = int((job.end_time - job.start_time).total_seconds())
                job.save(update_fields=['end_time', 'status', 'execution_time'])
            logger.info(f"Completed job: {job.job_name}")

        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            with transaction.atomic():
                job.status = Job.Status.FAILED
                job.end_time = timezone.now()
                job.save(update_fields=['status', 'end_time'])

        finally:
            with self.lock:
                self.active_jobs -= 1
                self._process_next_job()

    def _process_next_job(self):
        """Process the next job in the queue if slots are available."""
        if not self.priority_queue.empty() and self.active_jobs < self.executor._max_workers:
            _, _, _, next_job = self.priority_queue.get()
            if next_job.status == Job.Status.PENDING:  # Verify status
                self.active_jobs += 1
                self.executor.submit(self.execute_job, next_job)

    def load_pending_jobs(self, user):
        """Load user's pending jobs into the queue."""
        with self.lock:
            # Clear queue safely
            while not self.priority_queue.empty():
                self.priority_queue.get_nowait()

            # Annotate priority for ordering
            priority_order = Case(
                *[When(priority=k, then=Value(v)) for k, v in PRIORITY_MAP.items()],
                default=Value(0),
                output_field=IntegerField()
            )

            pending_jobs = Job.objects.filter(
                user=user, status=Job.Status.PENDING
            ).annotate(priority_order=priority_order).order_by('-priority_order', 'deadline')

            for job in pending_jobs:
                priority = PRIORITY_MAP.get(job.priority, 0)
                self.priority_queue.put((-priority, job.deadline, job.id, job))

# Global job manager instance
job_manager = JobManager()

class JobPagination:
    """Custom pagination settings."""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class JobViewSet(viewsets.ModelViewSet):
    """API endpoint for managing and processing jobs."""
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = JobPagination

    def get_queryset(self):
        """Return jobs for the authenticated user only."""
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create a job and queue it for processing."""
        job = serializer.save(user=self.request.user)
        job_manager.load_pending_jobs(self.request.user)  # Refresh queue
        job_manager.submit_job(job)

    def perform_update(self, serializer):
        """Handle job updates (e.g., priority changes)."""
        job = serializer.save()
        if job.status == Job.Status.PENDING:
            job_manager.load_pending_jobs(self.request.user)  # Re-sync queue

class RegisterView(APIView):
    """API endpoint for registering new users."""
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response('User registered', RegisterSerializer),
            400: 'Bad Request'
        }
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'User registered successfully',
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'user_id': user.id,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    """API endpoint for user login with JWT."""
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING),
                'password': openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=['username', 'password']
        ),
        responses={
            200: 'Login successful',
            400: 'Invalid credentials'
        }
    )
    async def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        user = await sync_to_async(authenticate)(username=username, password=password)
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'Login successful',
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'user_id': user.id,
            }, status=status.HTTP_200_OK)
        return Response({'message': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

class UserJobsView(APIView):
    """API endpoint to list jobs for a specific user."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        """Return paginated list of user's jobs."""
        if request.user.id != user_id:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        jobs = Job.objects.filter(user_id=user_id)
        paginator = JobPagination()
        page = paginator.paginate_queryset(jobs, request)
        serializer = JobSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
