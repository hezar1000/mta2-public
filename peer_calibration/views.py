import math, random, re, json, logging
from random import randint
from datetime import datetime


from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.contrib import messages
from django.forms import inlineformset_factory
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q, Max
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from django.shortcuts import render as djangoRender

from peer_home.wrappers import render

from peer_course.models import Course, CourseMember
from peer_course.base import CourseBase, CoursePermissions
from peer_assignment.models import Assignment, AssignmentSubmission, AssignmentQuestion
from peer_assignment.base import AssignmentBase
from peer_course.decorators import chosen_course_required
from peer_review.models import *
from peer_review.forms import *
from peer_review.views import ReviewViews
from peer_assignment.views import AssignmentViews
from peer_calibration.base import CalibrationBase
from peer_home.popup_widgets import PopupUtils
from peer_review.decorators import review_settings_required
from peer_grade.models import Appeal, InaptReport, InaptFlag

# Create your views here.


class CalibrationViews:
    @staticmethod
    def get_calibration(aid, gr):
        return (
            AssignmentSubmission._default_manager.filter(assignment__id=aid)
            .exclude(calibration_id=0)
            .exclude(reviewassignment__grader=gr)
        )

    @staticmethod
    @login_required
    @chosen_course_required
    def calibration_request(request, aid):

        render_dict = dict()
        render_dict["model_name"] = "review"

        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')
        course = get_object_or_404(Course, pk=request.session["course_id"])
        gr = CourseBase.get_course_member(request.user, course.id)

        if request.method == "GET":
            if CalibrationBase.get_calibrations(aid, gr) == -1:
                messages.warning(
                    request, "There are no more calibration reviews for this assigment!"
                )
                return HttpResponseRedirect(reverse("home:home"))
            else:
                calibrations = CalibrationBase.get_calibrations(aid, gr).order_by("?")
                review_assignment = ReviewAssignment._default_manager.create(
                    submission=calibrations[0], grader=gr
                )
                render_dict["model"] = review_assignment
                rcform = ReviewContentForm(
                    request.POST or None,
                    request.FILES or None,
                    instance=review_assignment,
                )
                render_dict["form"] = rcform
                render_dict["is_create"] = True
                return CalibrationViews.calibration_create(request, review_assignment.id)
        else:
            review_assignment = get_object_or_404(
                ReviewAssignment, pk=request.POST.get("rid", None)
            )
            render_dict["review"] = review_assignment
            rcform = ReviewContentForm(
                request.POST or None, request.FILES or None, instance=review_assignment
            )
            render_dict["review_form"] = rcform
            if rcform.is_valid():
                if review_assignment.submitted== True:
                    messages.error(
                        request, "You have already submitted a review for this calibration essay. Please try a new one."
                    )
                    return HttpResponseRedirect(
                        "/calibration/%s/view/" % request.POST.get("rid", None)
                    )

                rcform.save()
                if gr.is_independent:
                    dependability_estimate_16 = CalibrationBase.calculate_score_gibbs(gr,course,16)
                    dependability_estimate_15 = CalibrationBase.calculate_score_gibbs(gr,course,15)
                    # render_dict["dependability_estimate"]  = dependability_estimate
                    if dependability_estimate_16 < dependability_estimate_15 - 0.2:
                        flagged = InaptFlag._default_manager.create(review = review_assignment, reporter = gr, reason = 'decreases dependability')
                        


#                gr.lower_confidence_bound= dependability_min
#                gr.markingload= dependability_mean
#                gr.upper_confidence_bound= dependability_max
#                gr.save()
#                if not gr.is_independent:
#                    if gr.is_independent != CalibrationBase.check_if_independent(gr, course):
#                        gr.is_independent = CalibrationBase.check_if_independent(gr, course)
#                        gr.time_is_independent_changed = timezone.now()
#                        gr.save()
                # ReviewBase.save_review_files(rcform.cleaned_data,
                #     review_assignment, request)
                return HttpResponseRedirect(
                    "/calibration/%s/view/" % request.POST.get("rid", None)
                )

    @staticmethod
    @login_required
    @chosen_course_required
    def calibration_groundtruth_edit(request, rid):
        return HttpResponseRedirect(reverse("review:review_edit", kwargs={"rid": rid}))

    @staticmethod
    @login_required
    @chosen_course_required
    def calibration_assignment_edit(request, sid):
        """
        Edits an assignment submission made by the instructor/TAs.
        The students can then review this submission in order to get calibrated.
        """
        submission = get_object_or_404(AssignmentSubmission, pk=sid)
        CoursePermissions.require_course_staff(
            request.user, submission.assignment.course.id
        )
        cm = CourseBase.get_course_member(request.user, submission.assignment.course.id)

        ret_sub, scform = AssignmentViews.submission_edit_helper(
            request, submission, cm, enforce_deadline=False
        )
        if ret_sub is not None:

            messages.info(
                request,
                "Editing the calibration assignment was successful."
                + " You can now edit the correspnding correct (ground true) review if need be.",
            )

            review = ReviewAssignment._default_manager.filter(
                submission=submission, is_groundtruth=True
            ).first()

            if review is None:
                messages.error(
                    request, "Could not find corresponding review, creating a new one"
                )
                review = ReviewAssignment._default_manager.create(
                    submission=submission,
                    grader=cm,
                    is_groundtruth=True,
                    submitted=False,
                )

            return HttpResponseRedirect(
                reverse(
                    "calibration:calibration_groundtruth_edit",
                    kwargs={"rid": review.id},
                )
            )

        render_dict = dict()
        render_dict["assignment"] = submission.assignment
        render_dict["subform"] = scform
        render_dict["is_create"] = False
        return render(request, "submission-create.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def calibration_assignment_create(request, aid):
        """
        Creates an assignment submission made by the instructor/TAs.
        The students can then review this submission in order to get calibrated.
        """
        assignment = get_object_or_404(Assignment, pk=aid)

        if assignment.get_review_settings() is None:
            messages.warning(
                request,
                "Please configure the assignment settings and setup the rubrics first.",
            )
            return HttpResponseRedirect(reverse("assignment:list_for_course"))

        ## even a superuser cannot create calibration assignments
        ## as they don't have a corresponding CourseMember object
        CoursePermissions.require_course_staff(
            request.user, assignment.course.id, superuser_fine=False
        )
        cm = CourseBase.get_course_member(request.user, assignment.course.id)

        submission, scform = AssignmentViews.submission_creation_helper(
            request, assignment, cm, enforce_deadline=False
        )

        if submission is not None:
            AssignmentViews.display_form_warnings(request, scform)

            submission.calibration_id = 1 + max(
                0,
                AssignmentSubmission._default_manager.all().aggregate(
                    max=Max("calibration_id")
                )["max"],
            )

            submission.save()

            messages.info(
                request,
                "Calibration assignment created."
                + " You can now create the correspnding correct (ground true) review.",
            )

            review = ReviewAssignment._default_manager.create(
                submission=submission, grader=cm, is_groundtruth=True, submitted=False
            )

            return HttpResponseRedirect(
                reverse(
                    "calibration:calibration_groundtruth_edit",
                    kwargs={"rid": review.id},
                )
            )

        render_dict = dict()
        render_dict["assignment"] = assignment
        render_dict["subform"] = scform
        render_dict["is_create"] = True
        return render(request, "submission-create.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def calibration_create(request, rid):
        return ReviewViews.review_create(request, rid)

    @staticmethod
    @login_required
    @chosen_course_required
    def calibration_view(request, rid):
        render_dict = dict()
        course = get_object_or_404(Course, pk=request.session["course_id"])
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        review = get_object_or_404(ReviewAssignment, pk=rid)
        if ReviewAssignment._default_manager.filter(
            submission=review.submission, is_groundtruth=True
        ).exists():
            groundtruth = ReviewAssignment._default_manager.filter(
                submission=review.submission, is_groundtruth=True
            ).first()
            if ReviewContent._default_manager.filter(
                review_assignment=groundtruth
            ).exists():
                groundtruth_review = groundtruth
            else:
                return HttpResponseForbidden(
                    "There is no groundtruth review for this assignment. Please contact the course staff"
                )
        else:
            return HttpResponseForbidden(
                "There is no groundtruth review for this assignment. Please contact the course staff"
            )

        render_dict["review"] = review
        render_dict["components"] = {}
        render_dict["is_author"] = request.user == review.grader.user

        # TODO: give access to the submission author too, maybe?

        if not render_dict["is_author"] and not request.user.is_superuser:

            # It's not the submission author nor the grader, then it must be one of staff
            if course.can_tas_see_reviews and review.grader.role == "student":
                permission_req = CoursePermissions.require_course_staff
            else:
                permission_req = CoursePermissions.require_instructor

            permission_req(request.user, review.submission.assignment.course.id)


        (cal_dict, obtained_points,total_points) = CalibrationBase.calculate_calibration_points(review)
        render_dict.update(cal_dict)
        render_dict["dependability_min"]= round(review.grader.lower_confidence_bound,3)
        render_dict["dependability_mean"]= round(review.grader.markingload,3)

#        render_dict["dependability_min"]= round(CalibrationBase.convert_dependability_to_grade(review.grader.lower_confidence_bound),3)
#        render_dict["dependability_mean"]= round(CalibrationBase.convert_dependability_to_grade(review.grader.markingload),3)

#        render_dict["dependability_max"]= round(review.grader.upper_confidence_bound,2)

#        percentage= CalibrationBase.round_up((obtained_points/total_points)*100,2)
#        render_dict["points"] = percentage
        if InaptFlag._default_manager.filter(review = review).exists():
            render_dict["is_flagged"] = True
        render_dict["time_period"] = "Implied by the essay."
        return render(request, "calibration-view.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    @review_settings_required
    def assign_calibration_reviews(request, aid):
        "Assign calibration reviews"

        assignment = Assignment._default_manager.get(pk=aid)
        render_dict = dict()

        awr = AssignmentWithReviews._default_manager.get(pk=aid)

        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        render_dict["assignment"] = assignment
        render_dict["cid"] = assignment.course.id

        rubrics = Rubric._default_manager.all()
        render_dict["rubrics"] = rubrics

        if request.method == "POST":

            try:
                num_calibration_reviews = int(
                    request.POST.get("numcalibrationreviews", 3)
                )
                print("num of calibration reviews i %s" % num_calibration_reviews)
            except ValueError:
                messages.error(
                    request, "The number of reviews entered is not a valid integer."
                )
                return render(
                    request, "review-assign-calibration-reviews.html", render_dict
                )

            num_calibration_submissions = (
                AssignmentSubmission._default_manager.all()
                .exclude(calibration_id=0)
                .exclude(assignment__id=aid)
                .count()
            )
            print("num of calibration submissions is %s" % num_calibration_submissions)
            if num_calibration_reviews > (num_calibration_submissions):
                messages.error(
                    request,
                    "There is a total of %s calibration submissions. "
                    "It is impossible to assign %s calibration review per supervised student."
                    % (num_calibration_submissions, num_calibration_reviews),
                )
                return render(
                    request, "review-assign-calibration-reviews.html", render_dict
                )

            deadline = awr.student_review_deadline_default
            # rubric_id = awr.rubric_default.id

            CalibrationBase.assign_calibration_reviews(aid, num_calibration_reviews)

            return HttpResponseRedirect("/review/list_for_course/")

        return render(request, "review-assign-calibration-reviews.html", render_dict)
