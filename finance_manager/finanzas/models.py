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

    def porcentaje_ahorro(self):
        if self.meta_ahorro == 0:
            return 0
        return round((self.ahorro_actual / self.meta_ahorro) * 100, 2)

    def total_gastos(self):
        return sum([g.monto for g in Gasto.objects(usuario=self)])

    def total_ingresos(self):
        return sum([i.monto for i in Ingreso.objects(usuario=self)])

    def saldo_restante(self):
        return self.sueldo_base + self.total_ingresos() - self.total_gastos()


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
