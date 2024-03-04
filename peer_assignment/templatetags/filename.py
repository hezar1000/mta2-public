import os

from django import template

register = template.Library()


@register.filter
def filename(value):
    try:
        fname = os.path.basename(value.file.name)
        return fname
    except FileNotFoundError:
        return "error..."
