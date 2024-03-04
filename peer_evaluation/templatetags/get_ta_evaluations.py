from django import template

register = template.Library()

from peer_evaluation.models import EvaluationAssignment


def get_ta_evaluations(assignment):

    reviews_all = EvaluationAssignment._default_manager.filter(
        review__submission__assignment=assignment
    )
    reviews_ta = reviews_all.filter(grader__role="ta")
    return reviews_ta


register.filter("get_ta_evaluations", get_ta_evaluations)
