from django import template

register = template.Library()

from peer_review.models import ReviewAssignment


@register.simple_tag
def get_my_reviews(assignment, user):
    return ReviewAssignment._default_manager.filter(
        submission__assignment=assignment, grader__user=user
    )
