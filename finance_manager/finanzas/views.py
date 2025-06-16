from django.http import Http404
from .forms import CategoriaForm, GastoForm
from mongoengine import DoesNotExist
from .models import Gasto, Categoria, Usuario, Ingreso, GastoEsencial
from django.shortcuts import get_object_or_404, render, redirect
from datetime import datetime, timedelta, date
import calendar
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from django.http import HttpResponse
import io
import matplotlib.pyplot as plt
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import cm


# Vistas

# Vista para crear un nuevo usuario
def crear_usuario(request):
    if request.method == 'POST':
        nombre = request.POST['nombre']
        email = request.POST['email']
        sueldo_base = float(request.POST['sueldo_base'])
        meta_ahorro = float(request.POST.get('meta_ahorro', 0))

        usuario = Usuario(
            nombre=nombre,
            email=email,
            sueldo_base=sueldo_base,
            meta_ahorro=meta_ahorro,
            ahorro_actual=0.0
        )
        usuario.save()

        # Procesar gastos esenciales iniciales
        descripciones = request.POST.getlist('gastos_esenciales_descripcion[]')
        montos = request.POST.getlist('gastos_esenciales_monto[]')
        fechas = request.POST.getlist('gastos_esenciales_fecha[]')

        for i in range(len(descripciones)):
            if descripciones[i] and montos[i] and fechas[i]:  # Solo crear si todos los campos están llenos
                gasto_esencial = GastoEsencial(
                    usuario=usuario,
                    descripcion=descripciones[i],
                    monto=float(montos[i]),
                    fecha_limite=datetime.strptime(fechas[i], '%Y-%m-%d').date(),
                    pagado=False
                )
                gasto_esencial.save()

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
        primer_dia_mes = date(fecha.year, fecha.month, 1)
        if fecha.month == 12:
            primer_dia_siguiente_mes = date(fecha.year + 1, 1, 1)
        else:
            primer_dia_siguiente_mes = date(fecha.year, fecha.month + 1, 1)
            
        gastos_mes = Gasto.objects(
            usuario=usuario,
            fecha__gte=primer_dia_mes,
            fecha__lt=primer_dia_siguiente_mes
        )
        total_gastos_mes = sum(g.monto for g in gastos_mes)
        gastos_mensuales.append(total_gastos_mes)
        
        # Obtener ingresos del mes
        ingresos_mes = Ingreso.objects(
            usuario=usuario,
            fecha__gte=primer_dia_mes,
            fecha__lt=primer_dia_siguiente_mes
        )
        total_ingresos_mes = sum(i.monto for i in ingresos_mes)
        ingresos_mensuales.append(total_ingresos_mes)

    # Obtener el mes y año seleccionados del filtro
    mes_filtro = request.GET.get('mes')
    anio_filtro = request.GET.get('anio')
    orden = request.GET.get('orden')

    # Obtener gastos e ingresos del mes actual por defecto
    hoy = date.today()
    primer_dia_mes = date(hoy.year, hoy.month, 1)
    if hoy.month == 12:
        primer_dia_siguiente_mes = date(hoy.year + 1, 1, 1)
    else:
        primer_dia_siguiente_mes = date(hoy.year, hoy.month + 1, 1)

    # Si hay filtro de mes y año, actualizar las fechas
    if mes_filtro and anio_filtro:
        mes = int(mes_filtro)
        anio = int(anio_filtro)
        primer_dia_mes = date(anio, mes, 1)
        if mes == 12:
            primer_dia_siguiente_mes = date(anio + 1, 1, 1)
        else:
            primer_dia_siguiente_mes = date(anio, mes + 1, 1)

    # Filtrar gastos e ingresos por el mes seleccionado
    gastos = Gasto.objects.filter(
        usuario=usuario,
        fecha__gte=primer_dia_mes,
        fecha__lt=primer_dia_siguiente_mes
    )
    ingresos = Ingreso.objects.filter(
        usuario=usuario,
        fecha__gte=primer_dia_mes,
        fecha__lt=primer_dia_siguiente_mes
    )
    gastos_esenciales = GastoEsencial.objects.filter(usuario=usuario)

    if orden == 'mayor':
        gastos = gastos.order_by('-monto')
        ingresos = ingresos.order_by('-monto')
    elif orden == 'menor':
        gastos = gastos.order_by('monto')
        ingresos = ingresos.order_by('monto')

    # Calcular totales del mes seleccionado
    total_gastos = sum(g.monto for g in gastos)
    total_ingresos = sum(i.monto for i in ingresos)

    # Calcular total de gastos esenciales pagados y pendientes
    gastos_esenciales_pagados = sum(g.monto for g in gastos_esenciales if g.pagado)
    gastos_esenciales_pendientes = sum(g.monto for g in gastos_esenciales if not g.pagado)

    # El saldo restante ahora considera el saldo disponible y los gastos del mes actual
    saldo_restante = usuario.saldo_restante()
    porcentaje_ahorro = usuario.porcentaje_ahorro()

    # Resumen por categoría
    resumen_categorias = []
    categorias = Categoria.objects(usuario=usuario)
    
    # Datos para el gráfico de torta
    categorias_nombres = []
    gastos_por_categoria = []

    for categoria in categorias:
        # Obtener los gastos por categoría del mes seleccionado
        gastos_categoria = gastos.filter(categoria=categoria)
        total_categoria = sum(gasto.monto for gasto in gastos_categoria)

        # Agregar datos para el gráfico
        if total_categoria > 0:  # Solo incluir categorías con gastos
            categorias_nombres.append(categoria.nombre)
            gastos_por_categoria.append(total_categoria)

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

    # Generar lista de meses en español
    meses_es = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]
    meses_selector = []
    for i in range(1, 13):
        meses_selector.append({
            'valor': f"{i:02d}",
            'texto': meses_es[i-1]
        })
    # Generar lista de años para el selector
    anios_selector = list(range(hoy.year - 2, hoy.year + 2))

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
        'saldo_disponible': usuario.saldo_disponible,
        'porcentaje_ahorro': round(porcentaje_ahorro, 2),
        'mes_filtro': mes_filtro or str(hoy.month),
        'anio_filtro': anio_filtro or str(hoy.year),
        'orden_filtro': orden or '',
        'resumen_categorias': resumen_categorias,
        'meses': meses,
        'gastos_mensuales': gastos_mensuales,
        'ingresos_mensuales': ingresos_mensuales,
        'now': date.today(),
        'categorias_nombres': categorias_nombres,
        'gastos_por_categoria': gastos_por_categoria,
        'meses_selector': meses_selector,
        'anios_selector': anios_selector,
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

        # Calcular saldo disponible considerando el mes actual
        saldo_restante = usuario.saldo_restante()
        gastos_esenciales_pendientes = sum(g.monto for g in GastoEsencial.objects(usuario=usuario, pagado=False))

        # Validar si hay suficiente saldo considerando gastos esenciales pendientes
        if monto > (saldo_restante - gastos_esenciales_pendientes):
            categorias = Categoria.objects.filter(usuario=usuario)
            mensaje_error = f"⚠️ Saldo insuficiente: Solo tienes ${saldo_restante - gastos_esenciales_pendientes} disponibles para gastos no esenciales. "
            if gastos_esenciales_pendientes > 0:
                mensaje_error += f"Tienes ${gastos_esenciales_pendientes} en gastos esenciales pendientes que deben ser pagados primero."
            return render(request, 'agregar_gasto.html', {
                'usuario': usuario,
                'categorias': categorias,
                'error': mensaje_error,
                'saldo_restante': saldo_restante,
                'monto_ingresado': monto
            })

        # VALIDACIÓN del límite por categoría
        if categoria and categoria.limite_gasto:
            # Obtener gastos de la categoría del mes actual
            primer_dia_mes = date.today().replace(day=1)
            if date.today().month == 12:
                primer_dia_siguiente_mes = date(date.today().year + 1, 1, 1)
            else:
                primer_dia_siguiente_mes = date(date.today().year, date.today().month + 1, 1)
                
            total_gastado = sum(g.monto for g in Gasto.objects(
                usuario=usuario,
                categoria=categoria,
                fecha__gte=primer_dia_mes,
                fecha__lt=primer_dia_siguiente_mes
            ))
            
            if total_gastado + monto > categoria.limite_gasto:
                categorias = Categoria.objects.filter(usuario=usuario)
                return render(request, 'agregar_gasto.html', {
                    'usuario': usuario,
                    'categorias': categorias,
                    'error': f"⚠️ Límite superado: ya llevas ${total_gastado} de ${categoria.limite_gasto} en '{categoria.nombre}'"
                })

        # Guardar si está dentro del límite y hay saldo suficiente
        nuevo_gasto = Gasto(
            usuario=usuario,
            descripcion=descripcion,
            monto=monto,
            categoria=categoria,
            fecha=date.today(),
            hora=datetime.now()
        )
        nuevo_gasto.save()

        return redirect(f'/usuario/{usuario.id}/')

    categorias = Categoria.objects.filter(usuario=usuario)
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

        # Calcular saldo disponible considerando el mes actual
        saldo_restante = usuario.saldo_restante()
        gastos_esenciales_pendientes = sum(g.monto for g in GastoEsencial.objects(usuario=usuario, pagado=False))

        # Validar si hay suficiente saldo considerando gastos esenciales pendientes
        if monto > (saldo_restante - gastos_esenciales_pendientes):
            categorias = Categoria.objects.filter(usuario=usuario)
            mensaje_error = f"⚠️ Saldo insuficiente: Solo tienes ${saldo_restante - gastos_esenciales_pendientes} disponibles para nuevos gastos esenciales. "
            if gastos_esenciales_pendientes > 0:
                mensaje_error += f"Tienes ${gastos_esenciales_pendientes} en gastos esenciales pendientes que deben ser pagados primero."
            return render(request, 'agregar_gasto_esencial.html', {
                'usuario': usuario,
                'categorias': categorias,
                'error': mensaje_error
            })

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


def exportar_pdf_mes(request, usuario_id):
    from calendar import month_name
    usuario = Usuario.objects.get(id=usuario_id)
    mes = int(request.GET.get('mes', date.today().month))
    anio = int(request.GET.get('anio', date.today().year))
    # Fechas del mes
    primer_dia_mes = date(anio, mes, 1)
    if mes == 12:
        primer_dia_siguiente_mes = date(anio + 1, 1, 1)
    else:
        primer_dia_siguiente_mes = date(anio, mes + 1, 1)
    # Filtrar datos
    ingresos = Ingreso.objects(usuario=usuario, fecha__gte=primer_dia_mes, fecha__lt=primer_dia_siguiente_mes)
    gastos = Gasto.objects(usuario=usuario, fecha__gte=primer_dia_mes, fecha__lt=primer_dia_siguiente_mes)
    total_ingresos = sum(i.monto for i in ingresos)
    total_gastos = sum(g.monto for g in gastos)
    saldo = usuario.sueldo_base + total_ingresos - total_gastos

    # --- GRAFICO DE TORTA (Gastos por categoría) ---
    categorias = Categoria.objects(usuario=usuario)
    categorias_nombres = []
    gastos_por_categoria = []
    colores_torta = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#8AC249', '#EA526F', '#23B5D3', '#279AF1']
    colores_usados = []
    for idx, categoria in enumerate(categorias):
        total_categoria = sum(g.monto for g in gastos if g.categoria == categoria)
        if total_categoria > 0:
            categorias_nombres.append(categoria.nombre)
            gastos_por_categoria.append(total_categoria)
            colores_usados.append(colores_torta[idx % len(colores_torta)])
    fig1, ax1 = plt.subplots(figsize=(4.5, 4.5), dpi=120)
    wedges, texts, autotexts = ax1.pie(
        gastos_por_categoria,
        labels=None,
        autopct='%1.1f%%' if gastos_por_categoria else None,
        colors=colores_usados if gastos_por_categoria else None,
        startangle=90,
        textprops={'fontsize': 12, 'color': 'black'}
    )
    ax1.set_title('Gastos por Categoría', fontsize=12)
    # Sin leyenda
    if not gastos_por_categoria:
        ax1.text(0.5, 0.5, 'Sin datos', ha='center', va='center')
    buf1 = io.BytesIO()
    plt.tight_layout()
    fig1.savefig(buf1, format='png', bbox_inches='tight')
    plt.close(fig1)
    buf1.seek(0)

    # --- GRAFICO DE TENDENCIA (últimos 6 meses) ---
    meses_tendencia = []
    gastos_mensuales = []
    ingresos_mensuales = []
    for i in range(5, -1, -1):
        fecha = datetime(anio, mes, 1) - timedelta(days=30*i)
        m = fecha.month
        a = fecha.year
        meses_tendencia.append(f"{month_name[m][:3]} {a}")
        primer_dia = date(a, m, 1)
        if m == 12:
            primer_dia_sig = date(a + 1, 1, 1)
        else:
            primer_dia_sig = date(a, m + 1, 1)
        gastos_mes = Gasto.objects(usuario=usuario, fecha__gte=primer_dia, fecha__lt=primer_dia_sig)
        ingresos_mes = Ingreso.objects(usuario=usuario, fecha__gte=primer_dia, fecha__lt=primer_dia_sig)
        gastos_mensuales.append(sum(g.monto for g in gastos_mes))
        ingresos_mensuales.append(sum(i.monto for i in ingresos_mes))
    fig2, ax2 = plt.subplots(figsize=(4, 2.2))
    ax2.plot(meses_tendencia, gastos_mensuales, marker='o', color='#e74c3c', label='Gastos')
    ax2.plot(meses_tendencia, ingresos_mensuales, marker='o', color='#27AE60', label='Ingresos')
    ax2.set_title('Tendencia Mensual', fontsize=10)
    ax2.set_ylabel('Monto ($)')
    ax2.legend(fontsize=8)
    ax2.grid(True, linestyle='--', alpha=0.5)
    plt.xticks(rotation=30, fontsize=8)
    plt.tight_layout()
    buf2 = io.BytesIO()
    fig2.savefig(buf2, format='png', bbox_inches='tight')
    plt.close(fig2)
    buf2.seek(0)

    # --- PDF ---
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="finanzas-{mes:02d}-{anio}.pdf"'
    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    y = height - 40
    # Encabezado
    p.setFillColorRGB(0.15, 0.35, 0.6)
    p.rect(0, height-60, width, 60, fill=1, stroke=0)
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica-Bold", 22)
    p.drawString(40, height-45, f"Resumen Financiero - {month_name[mes]} {anio}")
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica", 12)
    p.drawString(40, height-75, f"Usuario: {usuario.nombre} ({usuario.email})")
    y = height - 100
    # Resumen financiero y gráfico de torta alineados
    resumen_x = 40
    resumen_y = y
    grafico_x = 300
    grafico_y = y
    # Resumen financiero (columna izquierda)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(resumen_x, resumen_y, "Resumen:")
    resumen_y -= 20
    p.setFont("Helvetica", 12)
    p.drawString(resumen_x+20, resumen_y, f"Sueldo Base: ${usuario.sueldo_base:,.2f}")
    resumen_y -= 16
    p.drawString(resumen_x+20, resumen_y, f"Total Ingresos: ${total_ingresos:,.2f}")
    resumen_y -= 16
    p.drawString(resumen_x+20, resumen_y, f"Total Gastos: ${total_gastos:,.2f}")
    resumen_y -= 16
    p.drawString(resumen_x+20, resumen_y, f"Saldo del Mes: ${saldo:,.2f}")
    # Gráfico de torta (centrado y más compacto)
    grafico_centro_x = 370
    p.setFont("Helvetica-Bold", 13)
    p.drawString(grafico_centro_x-60, y, "Gastos por Categoría:")
    p.drawImage(ImageReader(buf1), grafico_centro_x-70, y-200, width=180, height=180, mask='auto')
    # Lista de categorías debajo del gráfico, centrada
    if categorias_nombres:
        leyenda_y = y-210
        leyenda_x = grafico_centro_x-70
        for idx, nombre in enumerate(categorias_nombres):
            p.setFillColor(colors.HexColor(colores_usados[idx]))
            p.rect(leyenda_x, leyenda_y, 10, 10, fill=1, stroke=0)
            p.setFillColorRGB(0,0,0)
            p.setFont("Helvetica", 10)
            p.drawString(leyenda_x+15, leyenda_y+2, nombre)
            leyenda_y -= 14
    y -= 220 + max(14*len(categorias_nombres), 0)
    y -= 20
    # Tablas de ingresos y gastos (vertical)
    p.setFont("Helvetica-Bold", 13)
    p.drawString(40, y, "Ingresos del Mes:")
    y -= 18
    ingresos_data = [["Fecha", "Descripción", "Monto"]]
    for ingreso in ingresos:
        ingresos_data.append([str(ingreso.fecha), ingreso.descripcion, f"${ingreso.monto:,.2f}"])
    if len(ingresos_data) == 1:
        ingresos_data.append(["-", "Sin ingresos", "-"])
    table_ingresos = Table(ingresos_data, colWidths=[70, 200, 70])
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#36A2EB')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 11),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ])
    table_ingresos.setStyle(style)
    table_ingresos.wrapOn(p, 0, 0)
    table_ingresos.drawOn(p, 40, y-15*len(ingresos_data))
    y -= 15*len(ingresos_data) + 20
    p.setFont("Helvetica-Bold", 13)
    p.drawString(40, y, "Gastos del Mes:")
    y -= 18
    gastos_data = [["Fecha", "Descripción", "Monto"]]
    for gasto in gastos:
        cat = gasto.categoria.nombre if gasto.categoria else "Sin categoría"
        gastos_data.append([str(gasto.fecha), f"{gasto.descripcion} ({cat})", f"${gasto.monto:,.2f}"])
    if len(gastos_data) == 1:
        gastos_data.append(["-", "Sin gastos", "-"])
    table_gastos = Table(gastos_data, colWidths=[70, 200, 70])
    table_gastos.setStyle(style)
    table_gastos.wrapOn(p, 0, 0)
    table_gastos.drawOn(p, 40, y-15*len(gastos_data))
    y -= 15*len(gastos_data) + 20
    p.showPage()
    p.save()
    return response


def perfil_usuario(request, usuario_id):
    usuario = Usuario.objects.get(id=usuario_id)
    if request.method == 'POST':
        usuario.nombre = request.POST.get('nombre', usuario.nombre)
        usuario.email = request.POST.get('email', usuario.email)
        usuario.sueldo_base = float(request.POST.get('sueldo_base', usuario.sueldo_base))
        usuario.meta_ahorro = float(request.POST.get('meta_ahorro', usuario.meta_ahorro))
        usuario.ahorro_actual = float(request.POST.get('ahorro_actual', usuario.ahorro_actual))
        usuario.save()
        return redirect('dashboard', usuario_id=usuario.id)
    return render(request, 'perfil_usuario.html', {'usuario': usuario})
