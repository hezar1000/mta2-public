from django.conf.urls import url

from .views import ReviewViews

urlpatterns = [
    url(r"^list/$", ReviewViews.list),
    url(r"^([0-9]+)/list/$", ReviewViews.list_for_course),
    url(r"^list_for_course/$", ReviewViews.list_for_course, name="list_for_course"),
    url(
        r"^my_reviews_of_other_submissions/$",
        ReviewViews.my_reviews_of_other_submissions,
        name="my_reviews",
    ),
    url(r"^reviews_of_my_submissions/$", ReviewViews.reviews_of_my_submissions),
    url(
        r"^list_priorities/$", 
        ReviewViews.list_priorities, 
        name="list_priorities"
    ),
    url(r"^([0-9]+)/assignment/create/$", ReviewViews.assignment_create),
    url(
        r"^(?P<aid>[0-9]+)/manage_review_settings/$",
        ReviewViews.manage_review_settings,
        name="manage_settings",
    ),
    url(
        r"^(?P<aid>[0-9]+)/assignment_review_list/$",
        ReviewViews.assignment_review_list,
        name="assignment_review_list",
    ),
    url(
        r"^(?P<aid>[0-9]+)/assign_student_reviews/$",
        ReviewViews.assign_student_reviews,
        name="assign_student_reviews",
    ),
        url(
        r"^(?P<aid>[0-9]+)/assign_student_reviews/upload$",
        ReviewViews.upload_student_reviews,
        name="upload_student_reviews",
    ),
    url(
        r"^(?P<aid>[0-9]+)/assign_spot_checks/$",
        ReviewViews.assign_spot_checks,
        name="assign_spot_checks",
    ),
    url(
        r"^(?P<aid>[0-9]+)/assign_spot_checks/upload$",
        ReviewViews.upload_spot_checks,
        name="upload_spot_checks",
    ),
    url(
        r"^(?P<aid>[0-9]+)/assign_spot_checks/upload_priorities$",
        ReviewViews.upload_spot_checking_priorities,
        name="upload_spot_checking_priorities",
    ),
    url(r"^([0-9]+)/assign_self_reviews/$", ReviewViews.assign_self_reviews),
    url(
        r"^(?P<sid>[0-9]+)/request_review/$",
        ReviewViews.request_review_submission,
        name="request_review",
    ),
    url(r"^([0-9]+)/request/$", ReviewViews.request_random_review),
    url(r"^([0-9]+)/request_next/$", ReviewViews.request_next_review),
    url(r"^rubric/list/$", ReviewViews.rubric_list, name="rubric_list"),
    url(r"^rubric/create/$", ReviewViews.rubric_create, name="rubric_create"),
    url(r"^rubric/(?P<rid>[0-9]+)/edit/$", ReviewViews.rubric_edit, name="rubric_edit"),
    url(
        r"^rubric/(?P<rid>[0-9]+)/duplicate/$",
        ReviewViews.rubric_duplicate,
        name="rubric_duplicate",
    ),
    url(
        r"^rubric/(?P<rid>[0-9]+)/delete/$",
        ReviewViews.rubric_delete,
        name="rubric_delete",
    ),
    url(
        r"^rubric/question/list/$",
        ReviewViews.rubric_question_list,
        name="rubric_question_list",
    ),
    url(
        r"^rubric/question/create/$",
        ReviewViews.rubric_question_create,
        name="rubric_question_create",
    ),
    url(
        r"^rubric/question/(?P<qid>[0-9]+)/edit/$",
        ReviewViews.rubric_question_edit,
        name="rubric_question_edit",
    ),
    url(
        r"^rubric/question/(?P<qid>[0-9]+)/delete/$",
        ReviewViews.rubric_question_delete,
        name="rubric_question_delete",
    ),
    url(r"^(?P<rid>[0-9]+)/create/$", ReviewViews.review_create, name="create"),
    url(r"^(?P<rid>[0-9]+)/view/$", ReviewViews.review_view, name="view"),
    url(r"^view/reason_viewed/(?P<content_id>[0-9]+)/$", ReviewViews.reason_viewed, name="reason_viewed"),
    url(r"^view/endorse/(?P<rid>[0-9]+)/$", ReviewViews.endorse, name="endorse"),
    url(r"^(?P<rid>[0-9]+)/edit/$", ReviewViews.review_edit, name="review_edit"),
    url(r"^(?P<rid>[0-9]+)/reassign/$", ReviewViews.review_reassign, name="reassign"),
]
