from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='dashboard-index'),
    path('backups/', views.backups, name='backups'),
    path('backups/download/<path:backup_name>/', views.backup_download, name='backup-download'),
    path('tables/', views.table_list, name='table-list'),
    path('tables/<str:table_name>/', views.table_detail, name='table-detail'),
    path('tables/<str:table_name>/new/', views.table_create, name='table-create'),
    path('tables/<str:table_name>/<path:pk>/edit/', views.table_edit, name='table-edit'),
    path('tables/<str:table_name>/<path:pk>/delete/', views.table_delete, name='table-delete'),
    path('tables/<str:table_name>/bulk-delete/', views.table_bulk_delete, name='table-bulk-delete'),
]
