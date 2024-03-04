from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect

from .models import Assignment, AssignmentWithReviews


def review_settings_required(function):
    def wrap(request, **kwargs):
        if "aid" in kwargs:
            assignment = Assignment._default_manager.get(pk=kwargs["aid"])
        elif "sid" in kwargs:
            assignment = Assignment._default_manager.get(
                assignmentsubmission__pk=kwargs["sid"]
            )

        if AssignmentWithReviews._default_manager.filter(pk=assignment.id).exists():
            return function(request, **kwargs)
        else:
            messages.error(
                request,
                (
                    'Please <a href="%s">configure review settings</a>'
                    + " for assignment %s before assigning reviews"
                )
                % (
                    reverse("review:manage_settings", kwargs={"aid": assignment.id}),
                    assignment.name,
                ),
            )
            return HttpResponseRedirect(reverse("review:list_for_course"))

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap
