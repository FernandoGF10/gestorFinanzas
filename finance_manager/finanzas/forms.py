from django import forms


# Formulario para crear o editar una categoría de gastos
class CategoriaForm(forms.Form):
    nombre = forms.CharField(max_length=100)
    limite_gasto = forms.FloatField(
        min_value=0.0,
        required=False,
        initial=0.0,
        label='Límite de gasto'
    )


# Formulario para registrar un nuevo gasto
class GastoForm(forms.Form):
    descripcion = forms.CharField(max_length=200)
    monto = forms.FloatField()
    fecha = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    categoria = forms.CharField(required=False)


# Formulario para registrar un gasto esencial
class GastoEsencialForm(forms.Form):
    descripcion = forms.CharField(max_length=200)
    monto = forms.FloatField()
    fecha_limite = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    categoria = forms.CharField(required=False)
