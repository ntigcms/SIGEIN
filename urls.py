from django.urls import path
from . import views

urlpatterns = [
    path('equipamentos/cadastrar/', views.cadastrar_equipamento, name='cadastrar_equipamento'),
]
