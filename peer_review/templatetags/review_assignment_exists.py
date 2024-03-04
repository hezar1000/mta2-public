from peer_assignment.models import AssignmentQuestion
from django import template

register = template.Library()


# TODO: should I really change the name?
def review_assignment_exists(rubric):
    return AssignmentQuestion._default_manager.filter(rubric=rubric).exists()


register.filter("review_assignment_exists", review_assignment_exists)
