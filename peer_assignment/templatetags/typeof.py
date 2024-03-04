import os

from django import template

register = template.Library()


@register.filter
def typeof(value):
    return value.__class__.__name__
