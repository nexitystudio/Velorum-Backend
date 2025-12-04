from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    ROLES = [
        ('admin', 'Admin'),
        ('operator', 'Operator'),
        ('client', 'Client'),
    ]
    role = models.CharField(max_length=20, choices=ROLES, default='client')
    address = models.TextField(blank=True, default='')
    email = models.EmailField(max_length=50,default='')
    phone = models.CharField(max_length=15, blank=True, default='')
    register_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users" 
