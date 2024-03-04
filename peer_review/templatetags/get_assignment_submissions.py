from django import template

register = template.Library()

from peer_assignment.models import Assignment, AssignmentSubmission


def get_assignment_submissions(assignment):
    submissions = AssignmentSubmission._default_manager.filter(
        assignment=assignment, calibration_id=0
    )
    return submissions


register.filter("get_assignment_submissions", get_assignment_submissions)
