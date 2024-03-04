from django import template

register = template.Library()


@register.inclusion_tag("peer_assignment/tags/submission-button.html")
def submission_edit_button(submission, classes="", title="Edit"):
    return {
        "assignment": submission.assignment,
        "classes": classes,
        "title": title,
        "target": "assignment:submission_edit",
        "id": submission.id,
    }


@register.inclusion_tag("peer_assignment/tags/submission-button.html")
def submission_create_button(assignment, classes="", title="Create"):
    return {
        "assignment": assignment,
        "classes": classes,
        "title": title,
        "target": "assignment:submission_create",
        "id": assignment.id,
    }
