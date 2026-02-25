from django.urls import path
from . import views

urlpatterns = [
    path('', views.bienvenido, name='bienvenido'),
    path('registro/', views.registro_usuario, name='registro'),
    path('login/', views.login, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout/', views.cerrar_sesion, name='logout'),
    path('estudiantes/', views.listar_estudiantes, name='listar_estudiantes'),
    path('estudiantes/añadir/', views.anadir_estudiante, name='anadir_estudiante'),
    path('estudiantes/eliminar/<str:estudiante_id>/', views.eliminar_estudiante, name='eliminar_estudiante'),
    path('estudiantes/editar/<str:estudiante_id>/', views.editar_estudiante, name='editar_estudiante')
]