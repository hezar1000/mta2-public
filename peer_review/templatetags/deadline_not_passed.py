from django import template

register = template.Library()

from django.utils import timezone

# Legacy
def deadline_not_passed(assignment):
    return not assignment.deadline_passed()


register.filter("deadline_not_passed", deadline_not_passed)
