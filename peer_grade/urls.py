from django.conf.urls import url

from .views import GradeViews, AppealViews, FlagViews

urlpatterns = [
    # set manual grade by the instructor/TA
    url(
        r"^component/(?P<cid>[0-9]+)/set_manual/$",
        GradeViews.set_manual_component_grade,
        name="set_manual_component_grade",
    ),
    url(
        r"^assignment/(?P<aid>[0-9]+)/export/$",
        GradeViews.export_assignment_grades,
        name="export_assigment",
    ),
    url(
        r"^assignment/(?P<aid>[0-9]+)/import/$",
        GradeViews.import_assignment_grades,
        name="import_assigment",
    ),
    url(
        r"^assignment/(?P<aid>[0-9]+)/upload_component/$",
        GradeViews.upload_component_grades,
        name="upload_component_grades",
    ),
    url(
        r"^assignment/(?P<aid>[0-9]+)/export_comp_ids/$",
        GradeViews.export_comp_ids,
        name="export_comp_ids",
    ),
    url(r"^appeal/(?P<sid>[0-9]+)/create/$", AppealViews.create, name="appeal_create"),
    url(r"^appeal/(?P<apid>[0-9]+)/view/$", AppealViews.view, name="appeal_view"),
    url(r"^appeal/(?P<apid>[0-9]+)/reopen/$", AppealViews.reopen, name="appeal_reopen"),
    url(
        r"^appeal/(?P<apid>[0-9]+)/respond/$",
        AppealViews.respond,
        name="appeal_respond",
    ),
    url(r"^appeal/(?P<cid>[0-9]+)/list/$", AppealViews.list, name="appeal_list"),
    url(
        r"^report/(?P<rid>[0-9]+)/create/$",
        FlagViews.report_review,
        name="report_review",
    ),
    url(r"^report/(?P<rid>[0-9]+)/view/$", FlagViews.report_view, name="report_view"),
    url(
        r"^report/(?P<rid>[0-9]+)/dismiss/$",
        FlagViews.report_dismiss,
        name="report_dismiss",
    ),
    url(r"^flag/(?P<rid>[0-9]+)/$", FlagViews.flag_review, name="flag_review"),
    url(r"^appeal_timer/", AppealViews.appeal_timer, name="appeal_timer"),
    url(r"^report_timer/", AppealViews.report_timer, name="report_timer"),
    url(r"^gradebook/$", GradeViews.show_grade_book, name="gradebook"),
    url(r"^upload_grading_items/$", GradeViews.upload_grading_items, name="upload_grading_items"),
    url(
        r"^gradebook/export/$",
        GradeViews.export_course_grades,
        name="export_course",
    ),
]
