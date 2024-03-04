from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect

from peer_assignment.models import Assignment
from .models import EvaluationSettings


def evaluation_settings_required(function):
    def wrap(request, *args, **kwargs):
        if "aid" in kwargs:
            assignment = Assignment._default_manager.get(pk=kwargs["aid"])
        elif "sid" in kwargs:
            assignment = Assignment._default_manager.get(
                assignmentsubmission__pk=kwargs["sid"]
            )
        elif "rid" in kwargs:
            assignment = Assignment._default_manager.get(
                assignmentsubmission__reviewassignment__pk=kwargs["rid"]
            )

        if EvaluationSettings._default_manager.filter(pk=assignment.id).exists():
            return function(request, *args, **kwargs)
        else:
            messages.error(
                request,
                (
                    'Please <a href="%s">configure evaluation settings</a>'
                    + " for assignment %s before assigning evaluations"
                )
                % (
                    reverse(
                        "evaluation:manage_settings", kwargs={"aid": assignment.id}
                    ),
                    assignment.name,
                ),
            )
            return HttpResponseRedirect(reverse("review:list_for_course"))

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap
