from django import template

register = template.Library()

from peer_review.models import ReviewContent, ReviewAssignment
from django.utils import timezone


@register.simple_tag
@register.filter
def get_reviews_to_be_completed(reviews):

    contents_completed = ReviewContent._default_manager.values_list(
        "review_assignment__id", flat=True
    ).distinct()
    reviews_completed = reviews.filter(id__in=contents_completed)

    reviews_pending = [
        r for r in reviews.exclude(id__in=contents_completed) if not r.deadline_passed()
    ]
    return reviews_pending
