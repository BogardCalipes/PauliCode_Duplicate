from django.contrib import admin
from .models import User

class UserAdmin(admin.ModelAdmin):
    list_display = ('school_id', 'first_name', 'last_name', 'user_type', 'image_tag')
    search_fields = ('school_id', 'first_name', 'last_name')
    list_filter = ('user_type',)
    ordering = ('school_id',)

admin.site.register(User, UserAdmin)
# Register your models here.
