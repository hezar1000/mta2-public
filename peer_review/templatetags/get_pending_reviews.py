from django import template

register = template.Library()

from peer_review.models import ReviewContent, ReviewAssignment


def get_pending_reviews(reviews):

    contents_completed = ReviewContent._default_manager.values_list(
        "review_assignment__id", flat=True
    ).distinct()
    reviews_completed = reviews.filter(id__in=contents_completed)
    reviews_pending = reviews.exclude(id__in=contents_completed)

    return reviews_pending


register.filter("get_pending_reviews", get_pending_reviews)


def get_completed_reviews(reviews):

    contents_completed = ReviewContent._default_manager.values_list(
        "review_assignment__id", flat=True
    ).distinct()
    reviews_completed = reviews.filter(id__in=contents_completed)

    return reviews_completed


register.filter("get_completed_reviews", get_completed_reviews)
