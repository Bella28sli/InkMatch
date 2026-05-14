from django.contrib import admin
from django.urls import include, path

from dashboard import views as dashboard_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard_views.landing, name='site-home'),
    path('panel/', include('dashboard.urls')),
]
