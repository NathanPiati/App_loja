from django import template
import builtins

register = template.Library()


@register.filter
def replace(value, arg):
    old, new = arg.split(',')
    return str(value).replace(old, new)


@register.filter
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})


@register.filter
def subtract(value, arg):
    return value - arg


@register.filter
def abs(value):
    return builtins.abs(value)
