from django.http import Http404
from .forms import CategoriaForm, GastoForm
from mongoengine import DoesNotExist
from .models import Gasto, Categoria, Usuario, Ingreso, GastoEsencial
from django.shortcuts import get_object_or_404, render, redirect
from datetime import datetime, timedelta, date
import calendar


# Vistas

# Vista para crear un nuevo usuario
def crear_usuario(request):
    if request.method == 'POST':
        nombre = request.POST['nombre']
        email = request.POST['email']
        sueldo_base = float(request.POST['sueldo_base'])
        meta_ahorro = float(request.POST['meta_ahorro'])

        usuario = Usuario(
            nombre=nombre,
            email=email,
            sueldo_base=sueldo_base,
            meta_ahorro=meta_ahorro,
            ahorro_actual=0.0
        )
        usuario.save()
        return redirect('seleccionar_usuario')
    # Mostrar el formulario en caso GET
    return render(request, 'crear_usuario.html')


# Vista para seleccionar a un usuario existente
def seleccionar_usuario(request):
    # Para simplificar, lista los usuarios para elegir uno y simular "login"
    usuarios = Usuario.objects()
    return render(request, 'seleccionar_usuario.html', {'usuarios': usuarios})


# Vista para mostrar dashboard de un usuario
def dashboard_usuario(request, usuario_id):
    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except DoesNotExist:
        return redirect('/')

    meses = []
    gastos_mensuales = []
    ingresos_mensuales = []
    
    for i in range(5, -1, -1):
        fecha = datetime.now() - timedelta(days=30*i)
        mes = fecha.strftime('%B %Y')
        meses.append(mes)
        
        # Obtener gastos del mes
        gastos_mes = Gasto.objects(
            usuario=usuario,
            fecha__gte=datetime(fecha.year, fecha.month, 1),
            fecha__lt=datetime(fecha.year, fecha.month + 1, 1) if fecha.month < 12 else datetime(fecha.year + 1, 1, 1)
        )
        total_gastos_mes = sum(g.monto for g in gastos_mes)
        gastos_mensuales.append(total_gastos_mes)
        
        # Obtener ingresos del mes
        ingresos_mes = Ingreso.objects(
            usuario=usuario,
            fecha__gte=datetime(fecha.year, fecha.month, 1),
            fecha__lt=datetime(fecha.year, fecha.month + 1, 1) if fecha.month < 12 else datetime(fecha.year + 1, 1, 1)
        )
        total_ingresos_mes = sum(i.monto for i in ingresos_mes)
        ingresos_mensuales.append(total_ingresos_mes)

    gastos = Gasto.objects.filter(usuario=usuario)
    ingresos = Ingreso.objects.filter(usuario=usuario)
    gastos_esenciales = GastoEsencial.objects.filter(usuario=usuario)

    fecha = request.GET.get('fecha')
    orden = request.GET.get('orden')

    if fecha:
        gastos = gastos.filter(fecha=fecha)
        ingresos = ingresos.filter(fecha=fecha)

    if orden == 'mayor':
        gastos = gastos.order_by('-monto')
        ingresos = ingresos.order_by('-monto')
    elif orden == 'menor':
        gastos = gastos.order_by('monto')
        ingresos = ingresos.order_by('monto')

    # Agregar los gastos utilizando la agregación de MongoEngine
    total_gastos = gastos.aggregate(*[{
        '$group': {
            '_id': None,
            'total': {'$sum': '$monto'}
        }
    }])

    total_gastos = next(total_gastos, {}).get('total', 0)

    # Agregar los ingresos
    total_ingresos = ingresos.aggregate(*[{
        '$group': {
            '_id': None,
            'total': {'$sum': '$monto'}
        }
    }])

    total_ingresos = next(total_ingresos, {}).get('total', 0)

    # Calcular total de gastos esenciales pagados y pendientes
    gastos_esenciales_pagados = sum(g.monto for g in gastos_esenciales if g.pagado)
    gastos_esenciales_pendientes = sum(g.monto for g in gastos_esenciales if not g.pagado)

    # El saldo restante ahora considera solo los gastos esenciales pagados
    saldo_restante = usuario.sueldo_base + total_ingresos - total_gastos - gastos_esenciales_pagados
    porcentaje_ahorro = usuario.porcentaje_ahorro()

    # Resumen por categoría
    resumen_categorias = []
    categorias = Categoria.objects(usuario=usuario)

    for categoria in categorias:
        # Obtener los gastos por categoría
        gastos_categoria = gastos.filter(categoria=categoria)
        total_categoria = sum(gasto.monto for gasto in gastos_categoria)

        # Obtener el límite de gasto de la categoría
        limite_categoria = categoria.limite_gasto
        if limite_categoria > 0:
            porcentaje = (total_categoria / limite_categoria) * 100
        else:
            porcentaje = 0

        resumen_categorias.append({
            'nombre': categoria.nombre,
            'gasto': total_categoria,
            'limite': limite_categoria,
            'porcentaje': min(porcentaje, 100),  # Asegura que no supere el 100%
            'id': str(categoria.id)  # Agregamos el ID de la categoría
        })

    context = {
        'usuario': usuario,
        'gastos': gastos,
        'ingresos': ingresos,
        'gastos_esenciales': gastos_esenciales,
        'total_gastos': total_gastos,
        'total_ingresos': total_ingresos,
        'gastos_esenciales_pagados': gastos_esenciales_pagados,
        'gastos_esenciales_pendientes': gastos_esenciales_pendientes,
        'saldo_restante': saldo_restante,
        'porcentaje_ahorro': round(porcentaje_ahorro, 2),
        'fecha_filtro': fecha or '',
        'orden_filtro': orden or '',
        'resumen_categorias': resumen_categorias,
        'meses': meses,
        'gastos_mensuales': gastos_mensuales,
        'ingresos_mensuales': ingresos_mensuales,
        'now': date.today(),
    }

    return render(request, 'dashboard.html', context)


# Vista para agregar un gasto
def agregar_gasto(request, usuario_id):
    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except DoesNotExist:
        return redirect('/')

    if request.method == 'POST':
        descripcion = request.POST.get('descripcion')
        monto = float(request.POST.get('monto'))
        categoria_id = request.POST.get('categoria')
        categoria = Categoria.objects.get(id=categoria_id) if categoria_id else None

        # VALIDACIÓN del límite por categoría
        if categoria and categoria.limite_gasto:
            total_gastado = sum(g.monto for g in Gasto.objects(usuario=usuario, categoria=categoria))
            if total_gastado + monto > categoria.limite_gasto:
                categorias = Categoria.objects.filter(usuario=usuario)
                return render(request, 'agregar_gasto.html', {
                    'usuario': usuario,
                    'categorias': categorias,
                    'error': f"⚠️ Límite superado: ya llevas ${total_gastado} de ${categoria.limite_gasto} en '{categoria.nombre}'"
                })

        # Guardar si está dentro del límite
        nuevo_gasto = Gasto(
            usuario=usuario,
            descripcion=descripcion,
            monto=monto,
            categoria=categoria,
            hora=datetime.now()
        )
        nuevo_gasto.save()

        return redirect(f'/usuario/{usuario.id}/')

    categorias = Categoria.objects.filter(usuario=usuario)  # Solo mostrar categorías del usuario actual
    return render(request, 'agregar_gasto.html', {'usuario': usuario, 'categorias': categorias})


# Vista para editar un gasto
def editar_gasto(request, gasto_id):
    try:
        gasto = Gasto.objects.get(id=gasto_id)
        usuario = gasto.usuario
    except DoesNotExist:
        return redirect('/')

    if request.method == 'POST':
        gasto.descripcion = request.POST.get('descripcion')
        gasto.monto = float(request.POST.get('monto'))
        categoria_id = request.POST.get('categoria')
        gasto.categoria = Categoria.objects.get(id=categoria_id) if categoria_id else None
        gasto.save()

        return redirect(f'/usuario/{usuario.id}/')

    categorias = Categoria.objects.filter(usuario=usuario)  # Solo mostrar categorías del usuario
    return render(request, 'editar_gasto.html', {'gasto': gasto, 'usuario': usuario, 'categorias': categorias})


# Vista para eliminar un gasto
def eliminar_gasto(request, gasto_id):
    try:
        gasto = Gasto.objects.get(id=gasto_id)
        usuario_id = gasto.usuario.id
        gasto.delete()
        return redirect(f'/usuario/{usuario_id}/')
    except DoesNotExist:
        return redirect('/')


# Vista para mostrar la lista de categorías asociadas a un usuario
def lista_categorias(request, usuario_id):
    try:
        usuario = Usuario.objects.get(id=usuario_id)
        categorias = Categoria.objects.filter(usuario=usuario)
    except (DoesNotExist, TypeError):
        return redirect('seleccionar_usuario')

    return render(request, 'categorias/lista.html', {
        'categorias': categorias,
        'usuario_id': usuario_id,
        'usuario': usuario
    })


# Vista para crear una categoria
def crear_categoria(request):
    usuario_id = request.GET.get('usuario_id')
    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except (DoesNotExist, TypeError):
        return redirect('seleccionar_usuario')

    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = Categoria(
                nombre=form.cleaned_data['nombre'],
                limite_gasto=form.cleaned_data.get('limite_gasto', 0.0),
                usuario=usuario
            )
            categoria.save()
            return redirect('lista_categorias', usuario_id=usuario.id)
        else:
            return render(request, 'categorias/form.html', {
                'form': form,
                'usuario_id': usuario.id,
                'usuario': usuario
            })
    else:
        form = CategoriaForm()

    return render(request, 'categorias/form.html', {
        'form': form, 
        'usuario_id': usuario.id,
        'usuario': usuario
    })


# Vista para editar una categoria
def editar_categoria(request, categoria_id):
    usuario_id = request.GET.get('usuario_id')
    try:
        usuario = Usuario.objects.get(id=usuario_id)
        categoria = Categoria.objects.get(id=categoria_id, usuario=usuario)
    except (DoesNotExist, TypeError):
        return redirect('seleccionar_usuario')

    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria.nombre = form.cleaned_data['nombre']
            categoria.limite_gasto = form.cleaned_data.get('limite_gasto', 0.0)
            categoria.save()
            return redirect('dashboard', usuario_id=usuario_id)
    else:
        form = CategoriaForm(initial={
            'nombre': categoria.nombre,
            'limite_gasto': categoria.limite_gasto
        })

    return render(request, 'categorias/form.html', {
        'form': form, 
        'categoria': categoria, 
        'usuario_id': usuario_id,
        'usuario': usuario
    })


# Vista para eliminar una categoria
def eliminar_categoria(request, categoria_id):
    try:
        categoria = Categoria.objects.get(id=categoria_id)
        usuario_id = request.GET.get('usuario_id')
    except Categoria.DoesNotExist:
        raise Http404("Categoría no encontrada")

    # Si es una solicitud POST, eliminamos la categoría
    if request.method == 'POST':
        categoria.delete()
        if usuario_id:
            return redirect('dashboard', usuario_id=usuario_id)
        return redirect('lista_categorias')

    # Si no es una solicitud POST, redirigimos a la lista directamente
    if usuario_id:
        return redirect('dashboard', usuario_id=usuario_id)
    return redirect('lista_categorias')


# vista para editar resumen de un usuario
def editar_resumen(request, usuario_id):
    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except DoesNotExist:
        return redirect('/')

    if request.method == 'POST':
        usuario.sueldo_base = float(request.POST.get('sueldo_base'))
        usuario.meta_ahorro = float(request.POST.get('meta_ahorro'))
        usuario.save()
        return redirect('dashboard', usuario_id=usuario.id)

    return render(request, 'editar_resumen.html', {'usuario': usuario})


# Vista para agregar un ingreso
def agregar_ingreso(request, usuario_id):
    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except DoesNotExist:
        return redirect('/')

    if request.method == 'POST':
        descripcion = request.POST.get('descripcion')
        monto = float(request.POST.get('monto'))

        nuevo_ingreso = Ingreso(
            usuario=usuario,
            descripcion=descripcion,
            monto=monto,
            hora=datetime.now()
        )
        nuevo_ingreso.save()

        return redirect(f'/usuario/{usuario.id}/')

    return render(request, 'agregar_ingreso.html', {'usuario': usuario})


# Vista para editar un ingreso
def editar_ingreso(request, ingreso_id):
    try:
        ingreso = Ingreso.objects.get(id=ingreso_id)
        usuario = ingreso.usuario
    except DoesNotExist:
        return redirect('/')

    if request.method == 'POST':
        ingreso.descripcion = request.POST.get('descripcion')
        ingreso.monto = float(request.POST.get('monto'))
        ingreso.save()

        return redirect(f'/usuario/{usuario.id}/')

    return render(request, 'editar_ingreso.html', {'ingreso': ingreso, 'usuario': usuario})


# Vista para eliminar un ingreso
def eliminar_ingreso(request, ingreso_id):
    try:
        ingreso = Ingreso.objects.get(id=ingreso_id)
        usuario_id = ingreso.usuario.id
        ingreso.delete()
        return redirect(f'/usuario/{usuario_id}/')
    except DoesNotExist:
        return redirect('/')


# Vista para actualizar ahorro de un usuario
def actualizar_ahorro(request, usuario_id):
    usuario = Usuario.objects.get(id=usuario_id)

    if request.method == 'POST':
        nuevo_ahorro = float(request.POST['ahorro_actual'])
        usuario.ahorro_actual += nuevo_ahorro  # Sumamos el nuevo monto al ahorro actual
        usuario.save()
        return redirect('dashboard', usuario_id=usuario.id)

    return render(request, 'actualizar_ahorro.html', {'usuario': usuario})


def eliminar_usuario(request, usuario_id):
    try:
        usuario = Usuario.objects.get(id=usuario_id)
        
        if request.method == 'POST':
            # Eliminar todos los gastos asociados
            Gasto.objects.filter(usuario=usuario).delete()
            # Eliminar todos los ingresos asociados
            Ingreso.objects.filter(usuario=usuario).delete()
            # Eliminar todas las categorías asociadas
            Categoria.objects.filter(usuario=usuario).delete()
            # Finalmente eliminar el usuario
            usuario.delete()
            return redirect('seleccionar_usuario')
            
        return render(request, 'eliminar_usuario.html', {'usuario': usuario})
    except DoesNotExist:
        return redirect('seleccionar_usuario')


# Vista para agregar un gasto esencial
def agregar_gasto_esencial(request, usuario_id):
    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except DoesNotExist:
        return redirect('/')

    if request.method == 'POST':
        descripcion = request.POST.get('descripcion')
        monto = float(request.POST.get('monto'))
        fecha_limite = datetime.strptime(request.POST.get('fecha_limite'), '%Y-%m-%d').date()
        categoria_id = request.POST.get('categoria')
        categoria = Categoria.objects.get(id=categoria_id) if categoria_id else None

        nuevo_gasto = GastoEsencial(
            usuario=usuario,
            descripcion=descripcion,
            monto=monto,
            categoria=categoria,
            fecha_limite=fecha_limite,
            pagado=False
        )
        nuevo_gasto.save()
        return redirect(f'/usuario/{usuario.id}/')

    categorias = Categoria.objects.filter(usuario=usuario)
    return render(request, 'agregar_gasto_esencial.html', {'usuario': usuario, 'categorias': categorias})


# Vista para editar un gasto esencial
def editar_gasto_esencial(request, gasto_id):
    try:
        gasto = GastoEsencial.objects.get(id=gasto_id)
        usuario = gasto.usuario
    except DoesNotExist:
        return redirect('/')

    if request.method == 'POST':
        gasto.descripcion = request.POST.get('descripcion')
        gasto.monto = float(request.POST.get('monto'))
        gasto.fecha_limite = datetime.strptime(request.POST.get('fecha_limite'), '%Y-%m-%d').date()
        categoria_id = request.POST.get('categoria')
        gasto.categoria = Categoria.objects.get(id=categoria_id) if categoria_id else None
        gasto.save()

        return redirect(f'/usuario/{usuario.id}/')

    categorias = Categoria.objects.filter(usuario=usuario)
    return render(request, 'editar_gasto_esencial.html', {'gasto': gasto, 'usuario': usuario, 'categorias': categorias})


# Vista para marcar un gasto esencial como pagado
def marcar_gasto_esencial_pagado(request, gasto_id):
    try:
        gasto = GastoEsencial.objects.get(id=gasto_id)
        usuario_id = gasto.usuario.id
        gasto.pagado = True
        gasto.fecha_pago = date.today()
        gasto.save()
        return redirect(f'/usuario/{usuario_id}/')
    except DoesNotExist:
        return redirect('/')


# Vista para eliminar un gasto esencial
def eliminar_gasto_esencial(request, gasto_id):
    try:
        gasto = GastoEsencial.objects.get(id=gasto_id)
        usuario_id = gasto.usuario.id
        gasto.delete()
        return redirect(f'/usuario/{usuario_id}/')
    except DoesNotExist:
        return redirect('/')
