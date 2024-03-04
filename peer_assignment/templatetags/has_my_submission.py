from django import template

register = template.Library()


@register.simple_tag
def has_my_submission(assignment, user):
    return assignment.assignmentsubmission_set.filter(author__user=user).exists()
