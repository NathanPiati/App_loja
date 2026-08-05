import base64
from django import template

register = template.Library()

@register.filter
def b64encode(value):
    if value:
        # Se for memoryview → converte para bytes
        if isinstance(value, memoryview):
            value = value.tobytes()
        # Se for string → converte para bytes
        if isinstance(value, str):
            value = value.encode()
        return base64.b64encode(value).decode()
    return ''
