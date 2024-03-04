from django import template

from peer_course.views import CourseBase
from peer_review.choices import MULTIPLECHOICE, FILE, TEXT
from peer_assignment.models import AssignmentQuestionMultipleChoice

register = template.Library()


def get_submission_contents(submission, extra, fields, include_questions):
    contents = list()

    for component in submission.components.all():
        if (
            include_questions is not None
            and component.question.id not in include_questions
        ):
            continue

        component_dict = dict()

        component_dict["question_type"] = component.question.category
        component_dict["question"] = component.question.description
        component_dict["component"] = component

        component_dict["extra"] = None
        if extra is not None and component.id in extra:
            component_dict["extra"] = extra[component.id]
        # print(component.id, component_dict["extra"])

        component_dict["fields"] = []
        for field in fields:
            if field.name.startswith("rq_%d_" % component.id):
                component_dict["fields"].append(field)

        if component.question.category == MULTIPLECHOICE:
            choice_id = int(component.content)
            chosen = AssignmentQuestionMultipleChoice._default_manager.get(pk=choice_id)
            component_dict["answer"] = chosen.choice_text

        elif component.question.category == TEXT:
            component_dict["answer"] = component.content

        elif component.question.category == FILE:
            component_dict["answer"] = component.attachment

        contents.append(component_dict)

    return contents


def _submission_view(
    user,
    submission,
    extra=None,
    extra_template="",
    fields=[],
    show_header=False,
    show_grade=False,
    show_details=False,
    show_statement=False,
    include_questions=None,
):

    render_dict = dict()
    render_dict["sub"] = submission
    render_dict["show_header"] = False
    render_dict["show_statement"] = show_statement
    render_dict["is_author"] = False

    # role of the current user
    is_ta = CourseBase.is_ta(user, submission.assignment.course.id)
    is_instructor = CourseBase.is_instructor(user, submission.assignment.course.id)

    render_dict["author_and_details_visible"] = False
    if user == submission.author.user:
        render_dict["author_and_details_visible"] = show_details
        render_dict["is_author"] = True
    if user.is_superuser:
        render_dict["author_and_details_visible"] = show_details
    if is_ta or is_instructor:
        render_dict["author_and_details_visible"] = show_details

    render_dict["is_staff"] = is_instructor or is_ta or user.is_superuser
    if render_dict["is_author"] or render_dict["is_staff"]:
        render_dict["show_grade"] = show_grade

    render_dict["contents"] = get_submission_contents(
        submission, extra, fields, include_questions
    )
    render_dict["extra_template"] = extra_template

    return render_dict


@register.inclusion_tag("submission-view.html")
def submission_view(user, submission):
    return _submission_view(
        user,
        submission,
        show_header=True,
        show_grade=True,
        show_details=True,
        show_statement=True,
    )


@register.inclusion_tag("submission-view.html")
def submission_view_form(user, submission, fields):
    return _submission_view(user, submission, fields=fields)


@register.inclusion_tag("submission-view.html")
def submission_view_form_q(user, submission, fields, include_questions):
    return _submission_view(
        user, submission, fields=fields, include_questions=include_questions
    )


@register.inclusion_tag("submission-view.html")
def submission_view_extra(user, submission, extra, extra_template):
    return _submission_view(
        user, submission, extra=extra, extra_template=extra_template
    )


@register.inclusion_tag("submission-view.html")
def submission_view_extra_q(user, submission, extra, extra_template, include_questions):
    return _submission_view(
        user,
        submission,
        extra=extra,
        extra_template=extra_template,
        include_questions=include_questions,
    )


@register.inclusion_tag("submission-view.html")
def submission_view_form_extra(user, submission, fields, extra, extra_template):
    return _submission_view(
        user, submission, fields=fields, extra=extra, extra_template=extra_template
    )
