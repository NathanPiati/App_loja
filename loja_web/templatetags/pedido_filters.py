from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def aggregate(items, field):
    return sum(float(item[field]) for item in items if field in item)

@register.filter
def multiply2(value, arg):
    return Decimal(str(value)) * Decimal(str(arg))

@register.filter
def divide(value, arg):
    try:
        return Decimal(str(value)) / Decimal(str(arg))
    except ZeroDivisionError:
        return Decimal('0.00')



@register.filter
def clean_number(value):
    print(f"clean_number input: {value}, type: {type(value)}")
    try:
        if value is None:
            return '0,00'
        # Converter Decimal explicitamente para float
        if isinstance(value, Decimal):
            value = float(value)
        return f'{value:.2f}'.replace('.', ',')
    except (ValueError, InvalidOperation, TypeError) as e:
        print(f"clean_number error: {e}")
        return '0,00'

@register.filter
def multiply(value, arg):
    print(f"multiply inputs: value={value}, arg={arg}, types: {type(value)}, {type(arg)}")
    try:
        # Converter Decimal explicitamente para float
        if isinstance(value, Decimal):
            value = float(value)
        if isinstance(arg, Decimal):
            arg = float(arg)
        return float(value) * float(arg)
    except (ValueError, InvalidOperation, TypeError) as e:
        print(f"multiply error: {e}")
        return 0.0



@register.filter
def count_unpaid_parcels(financeiros):
    return financeiros.filter(data_pagamento__isnull=True).count()        