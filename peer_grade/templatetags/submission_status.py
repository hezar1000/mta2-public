from django import template
from peer_review.models import AssignmentWithReviews, ReviewAssignment
from peer_review.choices import QUIZ_ASGN

register = template.Library()


@register.inclusion_tag("peer_grade/tags/submission-status.html")
def submission_status(submission, compact=False):
    render_dict = {
        "has_submission": False,
        "can_see_grade": False,
        "cant_appeal": compact,
        "show_helper": compact,
    }

    if submission is not None:
        render_dict["submission_id"] = submission.id
        render_dict["has_submission"] = True
        if submission.assignment.assignment_type == QUIZ_ASGN:
            render_dict["deadline_passed"] = True
            render_dict["cant_appeal"] = True
            render_dict["grade"] = submission.final_grade
            render_dict["can_see_grade"] = render_dict["grade"] is not None
            render_dict["max_grade"] = submission.assignment.max_total_grade
        if submission.ta_deadline_passed():
            render_dict["deadline_passed"] = True
            render_dict["appeal"] = submission.get_appeal()
            render_dict["grade"] = submission.final_grade
            render_dict["max_grade"] = submission.assignment.max_total_grade
            render_dict["can_see_grade"] = render_dict["grade"] is not None
        if ReviewAssignment.objects.filter(
            submission=submission, submitted= True, grader__role= 'ta'
        ).exists():
            render_dict["appeal"] = submission.get_appeal()
            render_dict["grade"] = submission.final_grade
            render_dict["max_grade"] = submission.assignment.max_total_grade
            render_dict["can_see_grade"] = render_dict["grade"] is not None

    return render_dict
