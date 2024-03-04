from django import template

register = template.Library()

from peer_review.models import ReviewAssignment


def has_review(course):
    return ReviewAssignment._default_manager.filter(
        submission__assignment__course=course
    ).exists()


register.filter("has_review", has_review)
