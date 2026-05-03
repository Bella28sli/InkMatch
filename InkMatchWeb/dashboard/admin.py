from django.contrib import admin
from django.contrib.auth.models import Group, User

admin.site.site_header = 'InkMatch Admin'
admin.site.site_title = 'InkMatch'
admin.site.index_title = 'Панель управления InkMatch'

admin.site.unregister(Group)
admin.site.unregister(User)


@admin.register(User)
class InkMatchUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
