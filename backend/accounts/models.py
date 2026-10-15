from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # Auth0 subject is the stable external identity. Never derive authority from email.
    auth0_sub = models.CharField(max_length=255, unique=True, null=True, blank=True)

    def __str__(self):
        return self.username
