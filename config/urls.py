from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/auth/', include('accounts.urls')),
    path('api/branches/', include('branches.urls')),
    path('api/staff/', include('staff.urls')),
    path('api/services/', include('services.urls')),
    path('api/vehicles/', include('vehicles.urls')),
    path('api/visits/', include('visits.urls')),
]