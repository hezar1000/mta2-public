from django.utils import timezone

from django import template

register = template.Library()


@register.inclusion_tag("assignment-view.html")
def assignment_view(assignment, is_student, is_instructor):

    render_dict = dict()
    render_dict["assignment"] = assignment
    render_dict["is_student"] = is_student
    render_dict["is_instructor"] = is_instructor
    render_dict["deadlinePassed"] = timezone.now() > assignment.deadline

    return render_dict
