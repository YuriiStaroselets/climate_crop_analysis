from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_csv, name='upload'),
    path('analytics/', views.analytics, name='analytics'),
    path('export/', views.export_csv, name='export'),
    path('map/', views.map_view, name='map'),
    path('ml/', views.train_models_by_category, name='ml'),
    path('ml/<str:mode>/', views.train_models_by_category, name='ml-mode'),
    path('predict/', views.predict_yield_by_region, name='predict'),
]
