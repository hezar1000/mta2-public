from django import template

register = template.Library()

from peer_review.models import ReviewAssignment


def get_ta_reviews(assignment):

    reviews_all = ReviewAssignment._default_manager.filter(
        submission__assignment=assignment
    )
    reviews_ta = reviews_all.filter(grader__role="ta")
    return reviews_ta


register.filter("get_ta_reviews", get_ta_reviews)
