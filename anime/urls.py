from django.urls import path

from anime import views

urlpatterns = [
    path('', views.tier_list, name='tier_list'),
    path('rate/', views.rate, name='rate'),
    path('rate/tierlist/', views.save_tierlist, name='save_tierlist'),
    path('<slug:slug>/', views.anime_detail, name='anime_detail'),
]
