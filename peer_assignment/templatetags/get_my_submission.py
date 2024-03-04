from django import template

register = template.Library()


@register.simple_tag
def get_my_submission(assignment, user):
    if assignment.assignmentsubmission_set.filter(author__user=user).exists():
        return assignment.assignmentsubmission_set.filter(author__user=user).first()
    else:
        return None
