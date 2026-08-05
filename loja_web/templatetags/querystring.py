from django import template

register = template.Library()

@register.simple_tag
def querystring(request_get, key, value):
    query = request_get.copy()
    query[key] = value
    return query.urlencode()
