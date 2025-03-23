import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from django.urls import re_path 
from channels.db import database_sync_to_async
from django.core.paginator import Paginator




# Set the default Django settings module for the 'asgi' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jobscheduler.settings')


class SimpleConsumer(AsyncWebsocketConsumer):
    async def connect(self):        
        await self.accept()

    async def disconnect(self, close_code):
        # Handle disconnection
        pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get("action")

        if action == "get_all_jobs":
            # Fetch all jobs for charts
            self.user = self.scope['url_route']['kwargs'].get('user', None)
            jobs = await self.get_all_jobs(self.user)
            await self.send(text_data=json.dumps({
                "action": "get_all_jobs",
                "jobs": jobs,
            }))

        elif action == "get_filtered_jobs":
            # Fetch filtered and paginated jobs for the table
            self.user = self.scope['url_route']['kwargs'].get('user', None)
            self.status = self.scope['url_route']['kwargs'].get('status', None)
            self.page = int(self.scope['url_route']['kwargs'].get('page', 1))
            self.limit = int(self.scope['url_route']['kwargs'].get('limit', 5))
            jobs, total_pages = await self.get_filtered_jobs(self.user, self.status, self.page, self.limit)
            await self.send(text_data=json.dumps({
                "action": "get_filtered_jobs",
                "jobs": jobs,
                "total_pages": total_pages,
            }))

    @database_sync_to_async
    def get_all_jobs(self,user):
        from jobs.models import Job
        from jobs.serializers import JobSerializer
        job_set = Job.objects.filter(user=user)
        serializer = JobSerializer(job_set, many=True)
        return serializer.data

    @database_sync_to_async
    def get_filtered_jobs(self, user, status, page, limit):
        from jobs.models import Job
        from jobs.serializers import JobSerializer
        if status == "ALL":
            job_set = Job.objects.filter(user=user)
        else:
            job_set = Job.objects.filter(user=user, status=status)

        paginator = Paginator(job_set, limit)
        total_pages = paginator.num_pages
        page_obj = paginator.page(page)

        serializer = JobSerializer(job_set, many=True)
        return serializer.data, total_pages
        pass


# Routing of the ASGI application
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter([
            re_path(r"^ws/jobs/(?P<status>\w+)/(?P<user>\d+)/(?P<page>\d+)/(?P<limit>\d+)/$", SimpleConsumer.as_asgi()),
        ])
    ),
})
