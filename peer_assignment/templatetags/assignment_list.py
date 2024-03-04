from django import template

register = template.Library()


@register.inclusion_tag("assignment-list-for-course.html")
def assignment_list(user, assignments, is_student, is_instructor):

    render_dict = dict()
    render_dict["user"] = user
    render_dict["assignments"] = assignments
    render_dict["is_student"] = is_student
    render_dict["is_instructor"] = is_instructor

    return render_dict
