from django.db import models
from django.contrib.auth.models import User

class Job(models.Model):
    STATUS_CHOICES=[('PENDING','PENDING'),
    ('RUNNING','RUNNING'),
    ('FAILED','FAILED'),
    ('COMPLETED','COMPLETED')]

    job_name=models.CharField(max_length=100,default=' ')
    priority=models.CharField(max_length=10,default='Low')
    deadline=models.DateTimeField()
    estimated_duration=models.IntegerField(default=0)
    start_time = models.DateTimeField(null=True, blank=True)  
    end_time = models.DateTimeField(null=True, blank=True)  
    status=models.CharField(max_length=10,choices=STATUS_CHOICES,default='PENDING')
    execution_time=models.IntegerField(default=0)
    user=models.ForeignKey(User, on_delete=models.CASCADE)
    created_date=models.DateTimeField(auto_now_add=True,null=True, blank=True)  
    






