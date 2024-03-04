from django import template

register = template.Library()


@register.inclusion_tag("list-files.html")
def list_files(rubric_question, review_assignment):

    review_content = rubric_question.reviewcontent_set.get(
        review_assignment__id=review_assignment.id
    )
    files = review_content.reviewcontentfile_set.all()

    render_dict = dict()
    render_dict["files"] = files
    return render_dict
