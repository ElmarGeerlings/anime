from django.urls import path

from anime import views

urlpatterns = [
    path('', views.tier_list, name='tier_list'),
    path('rate/', views.rate, name='rate'),
    path('rate/tierlist/', views.save_tierlist, name='save_tierlist'),
    path('display-name/', views.save_anime_display_name, name='save_anime_display_name'),
    path('<slug:slug>/', views.anime_detail, name='anime_detail'),
]
