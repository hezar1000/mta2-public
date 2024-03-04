from django import template

register = template.Library()


@register.inclusion_tag("submission-files.html")
def submission_files(submission, question):

    content = submission.submissioncomponent_set.get(question__id=question.id)
    files = content.submissioncomponentfile_set.all()

    render_dict = dict()
    render_dict["files"] = files
    return render_dict
