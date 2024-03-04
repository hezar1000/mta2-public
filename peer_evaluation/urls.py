from django.conf.urls import url

from .views import EvaluationViews

urlpatterns = [
    url(
        r"^(?P<aid>[0-9]+)/manage_evaluation_settings/$",
        EvaluationViews.manage_evaluation_settings,
        name="manage_settings",
    ),
    url(
        r"^(?P<aid>[0-9]+)/assign_student_evaluations/$",
        EvaluationViews.assign_student_evaluations,
        name="assign_student_evaluations",
    ),
    url(
        r"^(?P<aid>[0-9]+)/assign_spot_checks/$",
        EvaluationViews.assign_spot_checks,
        name="assign_spot_checks",
    ),
    url(r"^(?P<eid>[0-9]+)/create/$", EvaluationViews.evaluation_create, name="create"),
    url(r"^(?P<eid>[0-9]+)/view/$", EvaluationViews.evaluation_view, name="view"),
    url(r"^(?P<eid>[0-9]+)/edit/$", EvaluationViews.evaluation_edit, name="edit"),
    url(
        r"^(?P<rid>[0-9]+)/request_evaluation/$",
        EvaluationViews.request_review_evaluation,
        name="request_evaluation",
    ),
]
