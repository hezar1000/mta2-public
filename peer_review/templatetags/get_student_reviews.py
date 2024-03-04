from django import template

register = template.Library()

from peer_review.models import ReviewAssignment


def get_student_reviews(assignment):

    reviews_all = ReviewAssignment._default_manager.filter(
        submission__assignment=assignment
    )
    reviews_student = reviews_all.filter(
        grader__role="student", submission__calibration_id=0
    )
    return reviews_student


def get_student_calibration_reviews(assignment):

    reviews_all = ReviewAssignment._default_manager.filter(
        submission__assignment=assignment
    )
    reviews_student = reviews_all.filter(grader__role="student").exclude(
        submission__calibration_id=0
    )
    return reviews_student


register.filter("get_student_reviews", get_student_reviews)
register.filter("get_student_calibration_reviews", get_student_calibration_reviews)
