import math, random, re, json, logging

from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.contrib import messages

# from django.forms import inlineformset_factory
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q

from django.shortcuts import render as djangoRender

from peer_home.wrappers import render

from peer_course.models import Course, CourseMember, CourseParticipation
from peer_course.base import CourseBase, CoursePermissions
from peer_assignment.models import Assignment, AssignmentSubmission, AssignmentQuestion
from peer_course.decorators import chosen_course_required

from peer_review.models import AssignmentWithReviews, Rubric, ReviewAssignment
from peer_review.decorators import review_settings_required
from peer_review.base import ReviewBase

from peer_calibration.base import CalibrationBase

from .models import EvaluationSettings, EvaluationAssignment
from .base import EvaluationBase
from .forms import (
    EvaluationSettingsForm,
    EvaluationContentForm,
    AssignTAEvaluationsForm,
)
from .decorators import evaluation_settings_required


eventLogger = logging.getLogger("mta.events")


class EvaluationViews:
    @staticmethod
    @login_required
    @chosen_course_required
    def manage_evaluation_settings(request, aid):
        "Create/edit evaluation settings"

        render_dict = dict()

        # TODO: this shouldn't be here!!
        # We probably do not this for now but we'd keep it here
        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict["course"] = course
        render_dict["cid"] = course.id

        CoursePermissions.require_instructor(request.user, course.id)

        awr = get_object_or_404(AssignmentWithReviews, pk=aid)
        render_dict["awr"] = awr
        render_dict["assignment"] = awr.assignment
        eval_settings = EvaluationSettings._default_manager.filter(pk=aid).first()

        form = EvaluationSettingsForm(
            data=request.POST or None, awr=awr, instance=eval_settings
        )

        render_dict["form"] = form

        if form.is_valid():
            awr = form.save(commit=False)
            eventLogger.info(
                "Creating/editing evalution settings [aid: %s] (by %s): %s"
                % (str(aid), request.user.username, str(request.POST))
            )
            return HttpResponseRedirect(reverse("assignment:list_for_course"))

        render_dict["model_name"] = "evaluation"
        return render(request, "review-settings.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    @review_settings_required
    @evaluation_settings_required
    def assign_spot_checks(request, aid):

        assignment = get_object_or_404(Assignment, pk=aid)
        render_dict = dict()
        render_dict["model_name"] = "evaluation"

        evaluation_settings = EvaluationSettings._default_manager.filter(pk=aid).first()
        if evaluation_settings is None:
            messages.warning(
                'Please <a href="%s">configure evaluations</a> first'
                % reverse("evaluation:manage_evaluation_settings", kwargs={"aid": aid})
            )
            return HttpResponseRedirect(reverse("review:list_for_course"))

        CoursePermissions.require_course_staff(request.user, assignment.course.id)

        render_dict["assignment"] = assignment
        render_dict["cid"] = assignment.course.id

        form = AssignTAEvaluationsForm(request.POST or None, assignment=assignment)
        render_dict["form"] = form

        if form.fields["num_to_assign"].max_value < 1:
            messages.warning(
                request, "All reviews already have TAs assigned to evaluate them."
            )
            return HttpResponseRedirect(reverse("review:list_for_course"))

        if form.is_valid():
            assigned = EvaluationBase.assign_spot_checks(
                aid, form.cleaned_data["num_to_assign"], form.get_all_tas()
            )
            messages.success(
                request, "Successfully assigned %d TA evaluations." % assigned
            )
            return HttpResponseRedirect(reverse("review:list_for_course"))

        return render(request, "review-assign-spot-checks.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    @review_settings_required
    @evaluation_settings_required
    def assign_student_evaluations(request, aid):
        "Assign student evaluations"

        assignment = get_object_or_404(Assignment, pk=aid)
        render_dict = dict()

        evaluation_settings = EvaluationSettings._default_manager.filter(pk=aid).first()
        if evaluation_settings is None:
            messages.warning(
                'Please <a href="%s">configure evaluations</a> first'
                % reverse("evaluation:manage_evaluation_settings", kwargs={"aid": aid})
            )
            return HttpResponseRedirect(reverse("review:list_for_course"))

        CoursePermissions.require_instructor(request.user, assignment.course.id)

        render_dict["assignment"] = assignment
        render_dict["cid"] = assignment.course.id

        rubrics = Rubric._default_manager.all()
        render_dict["rubrics"] = rubrics
        render_dict["model_name"] = "evaluation"

        if request.method == "POST":

            try:
                num_independent = int(request.POST.get("numindependent", 3))
                num_supervised = int(request.POST.get("numsupervised", 3))
                print(
                    "num of independent evaluations is %s and num of supervised evaluations is %s"
                    % (num_independent, num_supervised)
                )
            except ValueError:
                messages.error(
                    request, "The number of evaluations entered is not a valid integer."
                )
                return render(
                    request, "review-assign-student-reviews.html", render_dict
                )

            # TODO check with Hedayat: is this right? do we even have independent/supervised reviews?
            num_independent_submissions = ReviewAssignment._default_manager.filter(
                submission__assignment__id=aid, grader__is_independent=True
            ).count()
            num_supervised_submissions = ReviewAssignment._default_manager.filter(
                submission__assignment__id=aid, grader__is_independent=False
            ).count()
            print(
                "num of independent submissions is %s and num of supervised submissions is %s"
                % (num_independent_submissions, num_supervised_submissions)
            )
            if (
                num_independent > (num_independent_submissions - 1)
                and num_independent != 0
            ):
                messages.error(
                    request,
                    "There is a total of %s independent submissions. "
                    "It is impossible to assign %s evaluations per independent submission."
                    % (num_independent_submissions, num_independent),
                )
                return render(
                    request, "review-assign-student-reviews.html", render_dict
                )
            elif (
                num_supervised > (num_supervised_submissions - 1)
                and num_supervised != 0
            ):
                messages.error(
                    request,
                    "There is a total of %s supervised submissions. "
                    "It is impossible to assign %s evaluations per supervised submission."
                    % (num_supervised_submissions, num_supervised),
                )
                return render(
                    request, "review-assign-student-reviews.html", render_dict
                )

            # deadline = awr.student_review_deadline_default
            # rubric_id = awr.rubric_default.id

            EvaluationBase.assign_student_evaluations(
                assignment, num_independent, num_supervised
            )

            return HttpResponseRedirect("/review/list_for_course/")

        return render(request, "review-assign-student-reviews.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def evaluation_create(request, eid):

        render_dict = dict()
        render_dict["model_name"] = "review evaluation"
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        evaluation_assignment = get_object_or_404(EvaluationAssignment, pk=eid)
        render_dict["model"] = evaluation_assignment

        course = evaluation_assignment.review.submission.assignment.course
        render_dict["course"] = course
        render_dict["cid"] = course.id

        if evaluation_assignment.grader.role == 'ta':
            participations = CourseParticipation.objects.filter(participant = evaluation_assignment.grader).order_by('-id')
            if participations.exists():
                if participations[0].participation_list == 11:  
                    messages.warning(
                        request,
                        "It seems like you have not started your timer yet!",
                    )
                    return HttpResponseRedirect(reverse("home:home"))  
            else: 
                messages.warning(
                    request,
                    "It seems like you have not started your timer yet!",
                )
                return HttpResponseRedirect(reverse("home:home"))  

        if evaluation_assignment.grader.user != request.user:
            if not review_assignment.evaluations.filter(
                grader__user=request.user
            ).exists():
                CoursePermissions.require_course_staff(request.user, course.id)

        if evaluation_assignment.grader.role != "student":
            render_dict["members"] = course.members.filter(
                Q(role="ta") | Q(role="instructor")
            )

        ecform = EvaluationContentForm(
            request.POST or None, request.FILES or None, instance=evaluation_assignment
        )
        render_dict["form"] = ecform

        render_dict["components"] = ReviewBase.get_review_components_dict(
            evaluation_assignment.review
        )

        if ecform.is_valid():
            ecform.save()
            review_status, _, evaluation_considered = CalibrationBase.calculate_score(
                evaluation_assignment.review.grader, course
            )
            if evaluation_assignment.review.grader.is_independent == False:
                if evaluation_assignment.review.grader.is_independent != review_status:
                    evaluation_assignment.review.grader.is_independent = review_status
                    evaluation_assignment.review.grader.time_is_independent_changed = timezone.now()
                    evaluation_assignment.review.grader.save()
            return HttpResponseRedirect("/evaluation/%s/view/" % eid)

        else:
            # TODO: messages.error(request, ecform.errors)
            render_dict["is_create"] = not evaluation_assignment.submitted
            return render(request, "evaluation-create.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def evaluation_edit(request, eid):
        return HttpResponseRedirect(reverse("evaluation:create", kwargs={"eid": eid}))

    @staticmethod
    @login_required
    @chosen_course_required
    @evaluation_settings_required
    def request_review_evaluation(request, rid):
        "Request to be assigned an evaluation for a specific review (requires staff)"

        review = get_object_or_404(ReviewAssignment, pk=rid)

        CoursePermissions.require_course_staff(
            request.user, review.submission.assignment.course.id
        )

        if review.grader.user == request.user:
            messages.warning(request, "You cannot evaluate your own review.")
            return HttpResponseRedirect(reverse("review:view", kwargs={"rid": rid}))

        evaluation = review.evaluations.filter(grader__user=request.user).first()

        if evaluation is not None:
            messages.warning(request, "Evaluation already exists")
            return HttpResponseRedirect(
                reverse("evaluation:view", kwargs={"eid": evaluation.id})
            )
        else:
            evaluation = EvaluationAssignment._default_manager.create(
                review=review,
                grader=CourseBase.get_course_member(
                    request.user, review.submission.assignment.course.id
                ),
            )
            return HttpResponseRedirect(
                reverse("evaluation:create", kwargs={"eid": evaluation.id})
            )

    @staticmethod
    @login_required
    @chosen_course_required
    def evaluation_view(request, eid):

        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict = dict()
        render_dict["model_name"] = "evaluation"
        render_dict["edit_link"] = "evaluation:edit"
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        evaluation = get_object_or_404(EvaluationAssignment, pk=eid)
        render_dict["model"] = evaluation
        render_dict["is_author"] = request.user == evaluation.grader.user
        review= evaluation.review
        # TODO: give access to the submission author too, maybe?

        if (
            not render_dict["is_author"] 
            and not request.user.is_superuser
            and not ReviewAssignment._default_manager.filter(submission= review.submission, grader__user= request.user).exists()
        ):
            if evaluation.review.grader.user != request.user:
                #     if not evaluation.deadline_passed():
                #         raise PermissionDenied('You cannot see the evaluation of your review, until the deadline of student evaluations is up.')
                # else:
                # It's not the submission author nor the grader, then it must be one of staff
                if (
                    course.can_tas_see_reviews
                    and evaluation.review.grader.role == "student"
                ):
                    permission_req = CoursePermissions.require_course_staff
                else:
                    permission_req = CoursePermissions.require_instructor

                permission_req(
                    request.user, evaluation.review.submission.assignment.course.id
                )

        rev_comps = ReviewBase.get_review_components_dict(evaluation.review)
        eval_comps = EvaluationBase.get_evaluation_components_dict(evaluation)

        render_dict["components"] = dict(
            [
                (
                    scid,
                    {
                        "review_contents": rev_comps.get(scid, []),
                        "evaluation_contents": eval_comps.get(scid, []),
                    },
                )
                for scid in rev_comps.keys()
            ]
        )

        return render(request, "evaluation-view.html", render_dict)
