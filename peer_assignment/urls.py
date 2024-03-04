from django.conf.urls import url

from .views import AssignmentViews

urlpatterns = [
    url(
        r"^list_for_course/$", AssignmentViews.list_for_course, name="list_for_course"
    ),  # display all assignments in all courses
    url(r"^list/$", AssignmentViews.list),  # display all assignments in all courses
    # managing assignments
    url(
        r"^(?P<aid>[0-9]+)/view/$", AssignmentViews.view, name="view"
    ),  # create an assignment
    url(r"^create/$", AssignmentViews.create, name="create"),  # create an assignment
    url(r"^(?P<aid>[0-9]+)/edit/$", AssignmentViews.edit),  # edit an assignment
    url(r"^(?P<aid>[0-9]+)/delete/$", AssignmentViews.delete),  # delete an assignment
    url(r"^(?P<aid>[0-9]+)/show/$", AssignmentViews.show),  # show an assignment
    url(r"^(?P<aid>[0-9]+)/hide/$", AssignmentViews.hide),  # hide an assignment
    # upload submissions (batch submit)
    url(
        r"^(?P<aid>[0-9]+)/batch_submit/$",
        AssignmentViews.batch_submit,
        name="batch_submit",
    ),
    url(r"^question/list/$", AssignmentViews.question_list),
    url(r"^question/create/$", AssignmentViews.question_create),
    url(r"^question/([0-9]+)/edit/$", AssignmentViews.question_edit),
    # managing submissions
    url(
        r"^([0-9]+)/submission/list/$", AssignmentViews.submission_list
    ),  # create a submission for  an assignment
    url(
        r"^(?P<aid>[0-9]+)/submission/create/$",
        AssignmentViews.submission_create,
        name="submission_create",
    ),  # create a submission for  an assignment
    url(
        r"^submission/(?P<sid>[0-9]+)/edit/$",
        AssignmentViews.submission_edit,
        name="submission_edit",
    ),
    url(r"^submission/([0-9]+)/delete/$", AssignmentViews.submission_delete),
    url(
        r"^submission/(?P<sid>[0-9]+)/view/$",
        AssignmentViews.submission_view,
        name="submission_view",
    ),
    url(
        r"^submission/(?P<sid>[0-9]+)/late_unit_override/$",
        AssignmentViews.late_unit_override,
        name="late_unit_override",
    ),
]
