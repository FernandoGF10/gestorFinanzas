from django.urls import path
from . import views

urlpatterns = [
    path('', views.seleccionar_usuario, name='seleccionar_usuario'),
    path('usuario/<str:usuario_id>/', views.dashboard_usuario, name='dashboard'),
    path('usuario/<str:usuario_id>/gasto/', views.agregar_gasto, name='agregar_gasto'),
    path('usuario/<str:usuario_id>/ingreso/', views.agregar_ingreso, name='agregar_ingreso'),
    path('usuario/<str:usuario_id>/ahorro/', views.actualizar_ahorro, name='actualizar_ahorro'),
    path('crear/', views.crear_usuario, name='crear_usuario'),
    path('usuario/<str:usuario_id>/eliminar/', views.eliminar_usuario, name='eliminar_usuario'),
    path('gasto/<str:gasto_id>/editar/', views.editar_gasto, name='editar_gasto'),
    path('gasto/<str:gasto_id>/eliminar/', views.eliminar_gasto, name='eliminar_gasto'),
    path('ingreso/<str:ingreso_id>/editar/', views.editar_ingreso, name='editar_ingreso'),
    path('ingreso/<str:ingreso_id>/eliminar/', views.eliminar_ingreso, name='eliminar_ingreso'),
    path('usuario/<str:usuario_id>/categorias/', views.lista_categorias, name='lista_categorias'),
    path('categorias/nueva/', views.crear_categoria, name='crear_categoria'),
    path('categorias/editar/<str:categoria_id>/', views.editar_categoria, name='editar_categoria'),
    path('categorias/eliminar/<str:categoria_id>/', views.eliminar_categoria, name='eliminar_categoria'),
    path('categoria/eliminar/<str:categoria_id>/', views.eliminar_categoria, name='eliminar_categoria'),
    path('usuario/<str:usuario_id>/editar-resumen/', views.editar_resumen, name='editar_resumen'),
]
