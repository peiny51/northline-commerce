from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class StoreUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("External identity", {"fields": ("auth0_sub",)}),)
