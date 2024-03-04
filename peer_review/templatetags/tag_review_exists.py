from django import template

register = template.Library()

from peer_review.models import ReviewContent


def tag_review_exists(review_obj):
    return ReviewContent._default_manager.filter(
        review_assignment__id=review_obj.id
    ).exists()


register.filter("tag_review_exists", tag_review_exists)
