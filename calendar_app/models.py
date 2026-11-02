from django.db import models
from django.contrib.auth.models import User


class Event(models.Model):
    class Profile(models.TextChoices):
        WORK = 'work', 'Work'
        SCHOOL = 'school', 'School'
        PERSONAL = 'personal', 'Personal'

    profile = models.CharField(max_length=8, choices=Profile.choices, default=Profile.PERSONAL)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    shared_with = models.ManyToManyField(User, blank=True, related_name='shared_events')
    title = models.CharField(max_length=100)
    date = models.DateField()
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.title} ({self.date})"


class CalendarShare(models.Model):
    READ = 'read'
    EDIT = 'edit'
    PERMISSION_CHOICES = [(READ, 'View only'), (EDIT, 'Can edit')]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendar_shares_owned')
    viewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendars_shared_with_me')
    permission = models.CharField(max_length=4, choices=PERMISSION_CHOICES, default=READ)

    class Meta:
        unique_together = ('owner', 'viewer')

    def __str__(self):
        return f"{self.owner.username}'s calendar shared with {self.viewer.username}"