from django import template

register = template.Library()

from peer_course.base import CourseBase


@register.simple_tag
def get_role(course, user):
    if user.is_superuser:
        return "superuser"
    else:
        return CourseBase.get_user_role(user, course.id)
