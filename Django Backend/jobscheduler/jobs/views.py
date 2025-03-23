from django.shortcuts import render
from rest_framework import viewsets
from .models import Job
from django.views import View
from .serializers import JobSerializer,RegisterSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from django.utils import timezone
from drf_yasg import openapi
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny,IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework_simplejwt.authentication import JWTAuthentication
from concurrent.futures import ThreadPoolExecutor
import time
from django.db.models import Case, When, Value, IntegerField
import queue
from rest_framework.pagination import PageNumberPagination
from asgiref.sync import async_to_sync, sync_to_async


executor = ThreadPoolExecutor(max_workers=3)
priority_queue = queue.PriorityQueue()
pending_jobs=[]
running_jobs=[]


PRIORITY_MAP = {"High": 3, "Medium": 2, "Low": 1}
class JobViewset(viewsets.ModelViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # Save the job and start processing jobs
        job = serializer.save()
        self.process_jobs() 

    def process_jobs(self):
        # Fetch and load pending jobs into the priority queue
        self.load_priority_queue()

        # If there are no pending jobs, stop the processing
        if priority_queue.empty():
            print("No pending jobs found.")
            return

        while len(running_jobs) < 3 and not priority_queue.empty():
            # Create a batch of jobs (limit to 3 concurrent jobs)
            (_, _, _, job) = priority_queue.get()
            if job.status == "PENDING":
                running_jobs.append(job)  # Track this job as running
                executor.submit(self.execute_job, job)

        # After processing a batch, reload the queue recursively
        if len(self.running_state) < 3 and not priority_queue.empty():
            # Recursively call process_jobs to check for new jobs
            self.process_jobs()

    def load_priority_queue(self):
        # Clear the existing priority queue before loading new jobs
        while not priority_queue.empty():
            priority_queue.get()

        # Define priority order for jobs based on their priority levels
        priority_cases = []
        for key, value in PRIORITY_MAP.items():
            priority_cases.append(When(priority=key, then=Value(value)))

        priority_order = Case(*priority_cases, default=Value(4), output_field=IntegerField())

        # Fetch all jobs with "PENDING" status and order them by priority and deadline
        running_jobs=Job.objects.filter(status="RUNNING")
        pending_jobs = Job.objects.filter(status="PENDING").annotate(priority_order=priority_order).order_by('-priority_order', 'deadline')

        # Insert jobs into the priority queue with their priority values and deadlines
        for job in pending_jobs:
            if job.status == "PENDING":
                priority = PRIORITY_MAP.get(job.priority, 4)  # Default priority is 4 (lowest)
                # Use negative priority to ensure higher-priority jobs are processed first
                priority_queue.put((-priority, job.deadline, job.id, job))

    def execute_job(self, job):
        try:
            job.start_time = timezone.now()
            job.status = "RUNNING"
            job.save()
            print(f"Running: {job.job_name} (Priority: {job.priority}, Deadline: {job.deadline})")
            time.sleep(job.estimated_duration)  # Simulate job execution

            # After job execution, mark it as completed
            job.status = "COMPLETED"
            job.end_time = timezone.now()
            execution_time_seconds = (job.end_time - job.start_time).total_seconds()
            job.execution_time = execution_time_seconds // 1  # Set execution time in seconds
            job.save()
            print(f"Completed: {job.job_name}")
            running_jobs.remove(job)

        except Exception as e:
            print(f"Error while executing job {job.id}: {e}")
            job.status = "FAILED"
            job.save()

        # After completing the job, recursively call process_jobs to check for new pending jobs
        self.process_jobs()

class RegisterView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=RegisterSerializer,  
        responses={201: openapi.Response('User registered successfully', RegisterSerializer)}
    )
    
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            return Response({
                'message': 'User registered successfully.',
                
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

@sync_to_async
def authenticate_user(username, password):
    # This will execute authenticate() in a non-blocking manner
    return authenticate(username=username, password=password)

class LoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING),
                'password': openapi.Schema(type=openapi.TYPE_STRING)
            },
        ),
        responses={
            200: openapi.Response('Login successful'),
            400: openapi.Response('Invalid credentials'),
        },
    )
    def post(self, request):
        # Use async_to_sync to handle the asynchronous code
        return async_to_sync(self.async_post)(request)

    async def async_post(self, request):
        # Extract username and password from the request
        username = request.data.get('username')
        password = request.data.get('password')

        # Await the authenticate_user coroutine
        user = await authenticate_user(username, password)

        if user is not None:
            # Authentication successful, generate JWT tokens
            refresh = await sync_to_async(RefreshToken.for_user)(user)
            access_token = str(refresh.access_token)
            return Response({
                'message': 'Login successful!',
                'access_token': access_token,
                'refresh_token': str(refresh),
                'user': user.id,
            }, status=status.HTTP_200_OK)

        return Response({'message': 'Invalid credentials!'}, status=status.HTTP_400_BAD_REQUEST)
    
      
class UserJobsView(APIView):
    def get(self, request, user_id):
        jobs = Job.objects.filter(user_id=user_id)
        serializer = JobSerializer(jobs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)