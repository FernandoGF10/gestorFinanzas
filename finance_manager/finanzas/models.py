from django.db import models
from mongoengine import Document, StringField, FloatField, DateField, ReferenceField, DateTimeField, BooleanField
from datetime import date, datetime


# Create your models here.

# Modelo para Usuario
class Usuario(Document):
    nombre = StringField(required=True, max_length=100)
    email = StringField(required=True, unique=True)
    sueldo_base = FloatField(required=True)
    meta_ahorro = FloatField(default=0)
    ahorro_actual = FloatField(default=0)
    saldo_disponible = FloatField(default=0)  # Saldo que sobra de meses anteriores
    fecha_ultimo_sueldo = DateField(default=date.today)  # Fecha del último sueldo recibido

    def porcentaje_ahorro(self):
        if self.meta_ahorro == 0:
            return 0
        return round((self.ahorro_actual / self.meta_ahorro) * 100, 2)

    def total_gastos_mes_actual(self):
        # Obtener el primer día del mes actual
        hoy = date.today()
        primer_dia_mes = date(hoy.year, hoy.month, 1)
        # Obtener el primer día del siguiente mes
        if hoy.month == 12:
            primer_dia_siguiente_mes = date(hoy.year + 1, 1, 1)
        else:
            primer_dia_siguiente_mes = date(hoy.year, hoy.month + 1, 1)
        
        return sum([g.monto for g in Gasto.objects(
            usuario=self,
            fecha__gte=primer_dia_mes,
            fecha__lt=primer_dia_siguiente_mes
        )])

    def total_ingresos_mes_actual(self):
        # Obtener el primer día del mes actual
        hoy = date.today()
        primer_dia_mes = date(hoy.year, hoy.month, 1)
        # Obtener el primer día del siguiente mes
        if hoy.month == 12:
            primer_dia_siguiente_mes = date(hoy.year + 1, 1, 1)
        else:
            primer_dia_siguiente_mes = date(hoy.year, hoy.month + 1, 1)
        
        return sum([i.monto for i in Ingreso.objects(
            usuario=self,
            fecha__gte=primer_dia_mes,
            fecha__lt=primer_dia_siguiente_mes
        )])

    def saldo_restante(self):
        hoy = date.today()
        # Si es un nuevo mes, calcular el sobrante del mes anterior y sumarlo al saldo disponible
        if hoy.month != self.fecha_ultimo_sueldo.month or hoy.year != self.fecha_ultimo_sueldo.year:
            # Calcular el primer y último día del mes anterior
            if hoy.month == 1:
                mes_anterior = 12
                anio_anterior = hoy.year - 1
            else:
                mes_anterior = hoy.month - 1
                anio_anterior = hoy.year
            primer_dia_mes_anterior = date(anio_anterior, mes_anterior, 1)
            if mes_anterior == 12:
                primer_dia_siguiente_mes_anterior = date(anio_anterior + 1, 1, 1)
            else:
                primer_dia_siguiente_mes_anterior = date(anio_anterior, mes_anterior + 1, 1)
            
            # Calcular ingresos y gastos del mes anterior
            ingresos_mes_anterior = sum([i.monto for i in Ingreso.objects(
                usuario=self,
                fecha__gte=primer_dia_mes_anterior,
                fecha__lt=primer_dia_siguiente_mes_anterior
            )])
            gastos_mes_anterior = sum([g.monto for g in Gasto.objects(
                usuario=self,
                fecha__gte=primer_dia_mes_anterior,
                fecha__lt=primer_dia_siguiente_mes_anterior
            )])
            sobrante_mes_anterior = self.sueldo_base + ingresos_mes_anterior - gastos_mes_anterior
            self.saldo_disponible += max(0, sobrante_mes_anterior)
            self.fecha_ultimo_sueldo = hoy
            self.save()
        # Calcular saldo del mes actual
        saldo = self.saldo_disponible + self.sueldo_base + self.total_ingresos_mes_actual() - self.total_gastos_mes_actual()
        return saldo


# Modelo para Categoria
class Categoria(Document):
    nombre = StringField(required=True, max_length=100)
    limite_gasto = FloatField(default=0)
    usuario = ReferenceField(Usuario, required=True)

    def __str__(self):
        return f"{self.nombre} (Límite: {self.limite_gasto})"


# Modelo para Gasto
class Gasto(Document):
    usuario = ReferenceField(Usuario, required=True)
    descripcion = StringField(required=True)
    monto = FloatField(required=True)
    categoria = ReferenceField(Categoria)
    fecha = DateField(default=date.today)
    hora = DateTimeField(default=datetime.now)


# Modelo para Ingreso
class Ingreso(Document):
    usuario = ReferenceField(Usuario, required=True)
    descripcion = StringField(required=True)
    monto = FloatField(required=True)
    fecha = DateField(default=date.today)
    hora = DateTimeField(default=datetime.now)


# Modelo para GastoEsencial
class GastoEsencial(Document):
    usuario = ReferenceField(Usuario, required=True)
    descripcion = StringField(required=True)
    monto = FloatField(required=True)
    categoria = ReferenceField(Categoria)
    fecha_limite = DateField(required=True)
    fecha_creacion = DateField(default=date.today)
    hora_creacion = DateTimeField(default=datetime.now)
    pagado = BooleanField(default=False)
    fecha_pago = DateField(null=True)

    def __str__(self):
        return f"{self.descripcion} - {self.monto} (Vence: {self.fecha_limite})"
