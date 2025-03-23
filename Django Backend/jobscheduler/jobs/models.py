from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

class Job(models.Model):
    """Represents a job/task with scheduling and status tracking."""
    
    # Choices as TextChoices for better type safety and reusability
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        RUNNING = 'RUNNING', 'Running'
        FAILED = 'FAILED', 'Failed'
        COMPLETED = 'COMPLETED', 'Completed'

    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'

    # Core fields with optimized definitions
    job_name = models.CharField(max_length=100, db_index=True)
    priority = models.CharField(
        max_length=6,  # Matches longest choice ('MEDIUM')
        choices=Priority.choices,
        default=Priority.LOW,
        db_index=True
    )
    deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    estimated_duration = models.PositiveSmallIntegerField(
        default=0,
        help_text="Estimated duration in minutes"
    )
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=9,  # Matches longest choice ('COMPLETED')
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='jobs',
        db_index=True
    )
    created_date = models.DateTimeField(auto_now_add=True, db_index=True)

    # Remove execution_time field; use property for dynamic calculation
    @property
    def execution_time(self):
        """Calculate execution time in minutes if start and end times are set."""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() / 60)
        return 0

    def clean(self):
        """Validate time-related fields."""
        if self.start_time and self.end_time and self.end_time < self.start_time:
            raise ValidationError("End time cannot be before start time.")
        if self.deadline and self.start_time and self.deadline < self.start_time:
            raise ValidationError("Deadline cannot be before start time.")

    def save(self, *args, **kwargs):
        """Optimize save by validating and setting defaults efficiently."""
        self.full_clean()  # Run validation
        super().save(*args, **kwargs)

    def transition_to(self, new_status):
        """Enforce valid status transitions."""
        valid_transitions = {
            self.Status.PENDING: [self.Status.RUNNING],
            self.Status.RUNNING: [self.Status.COMPLETED, self.Status.FAILED],
            self.Status.COMPLETED: [],
            self.Status.FAILED: [],
        }
        if new_status not in valid_transitions.get(self.status, []):
            raise ValueError(f"Invalid transition from {self.status} to {new_status}")
        self.status = new_status
        self.save(update_fields=['status'])  # Partial update for efficiency

    def __str__(self):
        return f"{self.job_name} ({self.status})"

    class Meta:
        # Optimize query performance with indexes
        indexes = [
            models.Index(fields=['user', 'status'], name='idx_user_status'),
            models.Index(fields=['deadline', 'priority'], name='idx_deadline_priority'),
        ]
        # Ensure unique job names per user (optional, based on use case)
        constraints = [
            models.UniqueConstraint(fields=['user', 'job_name'], name='unique_job_per_user')
        ]
        ordering = ['-created_date']  # Default ordering for queries
