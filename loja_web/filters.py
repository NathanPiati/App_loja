from django import forms

class VendasFilterForm(forms.Form):
    data_inicial = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Data Inicial'
    )
    data_final = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Data Final'
    )
