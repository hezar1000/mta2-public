import math, random, re, json, logging
from random import randint
from datetime import datetime

from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.contrib import messages
from django.forms import inlineformset_factory
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


from django.shortcuts import render as djangoRender

from peer_home.wrappers import render

from peer_course.models import Course, CourseMember, CourseParticipation
from peer_course.base import CourseBase, CoursePermissions
from peer_assignment.models import Assignment, AssignmentSubmission, AssignmentQuestion
from peer_assignment.base import AssignmentBase
from peer_course.decorators import chosen_course_required

from peer_home.popup_widgets import PopupUtils
from peer_evaluation.models import EvaluationAssignment
from peer_evaluation.base import  EvaluationBase
from peer_grade.models import Appeal, InaptReport, InaptFlag
from peer_grade.views import AppealViews
from peer_grade.forms import *

from .choices import *
from .models import *
from .forms import *
from .base import ReviewBase
from .decorators import review_settings_required


# This line creates dependency with the peer calibration app :( :
from peer_calibration.base import CalibrationBase

eventLogger = logging.getLogger("mta.events")

# Create your views here.

# TODO: permissionsss!!!! (CRITICAL!)
# TODO: view submission
# TODO: assign ....


class ReviewHelper:
    @staticmethod
    def preview(question):
        return (
            "<strong>"
            + question.title
            + ":</strong> "
            + question.text
            + "<ul>"
            + "".join(
                [
                    "<li>" + str(c.marks) + " : " + c.text + "</li>"
                    for c in question.choices.all()
                ]
            )
            + "</ul>"
        )

    @staticmethod
    def preview_questions(questions):
        return (
            json.dumps(dict([(q.id, ReviewHelper.preview(q)) for q in questions]))
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace('"', '\\"')
        )


class ReviewViews:
    @staticmethod
    @login_required
    @chosen_course_required
    def reviews_of_my_submissions(request):

        render_dict = dict()
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')
        # if not 'cid' in request.session:
        #    return render(request, 'reviews-of-my-submissions.html', render_dict)

        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict["course"] = course
        render_dict["cid"] = course.id
        print("course: ", course)

        render_dict["submissions"] = AssignmentSubmission._default_manager.filter(
            assignment__course=course,
            author=CourseBase.get_course_member(request.user, course.id),
        ).order_by("assignment__deadline")

        return render(request, "reviews-of-my-submissions.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def my_reviews_of_other_submissions(request):

        render_dict = dict()
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')
        # if not 'cid' in request.session:
        #    return render(request, 'my-reviews-of-other-submissions.html', render_dict)

        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict["course"] = course
        render_dict["cid"] = course.id

        render_dict["now"] = timezone.now()

        my_reviews = ReviewAssignment._default_manager.filter(
            submission__assignment__course=course,
            grader__user=request.user,
            submission__calibration_id=0,
        ).order_by("submission__assignment__deadline")
        render_dict["reviews"] = my_reviews

        return render(request, "my-reviews-of-other-submissions.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def list_for_course(request):
        "List all review assignments for this course"

        course = get_object_or_404(Course, pk=request.session["course_id"])
    
        cm = CourseBase.get_course_member(request.user, course.id)

        if not request.user.is_superuser:
            if cm.role == 'student' or cm.role == 'ta':
                return HttpResponseRedirect(reverse("review:my_reviews"))

        render_dict = dict()
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')
        # if not 'cid' in request.session:
        #    return render(request, 'review-list-for-course.html', render_dict)

        render_dict["course"] = course
        render_dict["cid"] = course.id

        render_dict["assignments"] = (
            Assignment._default_manager.filter(course=course)
            .exclude(deadline=None)
            .order_by("-deadline")
        )
        render_dict["reviews"] = ReviewAssignment._default_manager.filter(
            submission__assignment__course=course, grader__user=request.user
        )

        return render(request, "review-list-for-course.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def rubric_list(request):
        "Show the list of rubrics"

        course = get_object_or_404(Course, pk=request.session["course_id"])
        CoursePermissions.require_course_staff(request.user, course.id)

        render_dict = dict()
        render_dict["course"] = course
        render_dict["cid"] = course.id

        render_dict["rubrics"] = Rubric._default_manager.all()
        return render(request, "rubric-list.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def rubric_create(request):
        "Create a rubric"
        # TODO: make rubrics specific to courses

        return ReviewViews._handle_rubric_request(request, None)

    @staticmethod
    def _handle_rubric_request(request, rubric=None):
        """Handle creating/editing a rubric"""
        course = get_object_or_404(Course, pk=request.session["course_id"])

        CoursePermissions.require_course_staff(request.user, course.id)

        render_dict = dict()
        render_dict["course"] = course
        render_dict["cid"] = course.id
        render_dict["is_create"] = rubric is None

        render_dict["questions"] = ReviewHelper.preview_questions(
            RubricQuestion._default_manager.all().order_by('title')
        )

        if request.GET.get("popup", False):
            render_dict["remove_navbar"] = True
            render_dict["is_popup"] = True

        render_dict["form"] = rubric_form = RubricForm(
            data=request.POST or None, instance=rubric
        )

        if rubric_form.is_valid():
            rubric = rubric_form.save()
            if "popup" in request.POST:
                return PopupUtils.return_to_multiple_parents(
                    rubric._get_pk_val(), rubric
                )
            else:
                return HttpResponseRedirect(reverse("review:rubric_list"))
        else:
            # TODO: fix
            messages.error(request, rubric_form.errors)

        return render(request, "rubric-create.html", render_dict)

    @staticmethod
    @login_required
    def rubric_duplicate(request, rid):
        course = get_object_or_404(Course, pk=request.session["course_id"])
        CoursePermissions.require_course_staff(request.user, course.id)

        rubric = get_object_or_404(Rubric, pk=rid)
        questions = rubric.questions.all()
        rubric.id = None
        rubric.save()
        rubric.questions = questions
        rubric.save()
        return HttpResponseRedirect("/review/rubric/list/")

    @staticmethod
    @login_required
    def rubric_delete(request, rid):
        course = get_object_or_404(Course, pk=request.session["course_id"])
        CoursePermissions.require_course_staff(request.user, course.id)

        rubric = Rubric._default_manager.filter(pk=rid).first()
        if rubric is None:
            messages.error(request, "Rubric not found")
        else:
            requirer = AssignmentQuestion._default_manager.filter(rubric=rubric)
            if requirer.exists():
                messages.error(
                    request,
                    "Rubric is required by %d questions including %s"
                    % (requirer.count(), str(requirer.first())),
                )
            else:
                rubric.delete()

        return HttpResponseRedirect("/review/rubric/list/")

    @staticmethod
    @login_required
    @chosen_course_required
    def rubric_edit(request, rid):
        "Edit a rubric"

        rubric = Rubric._default_manager.get(pk=rid)

        return ReviewViews._handle_rubric_request(request, rubric)

    @staticmethod
    @login_required
    @chosen_course_required
    def rubric_question_create(request):
        "Create a rubric question"

        course = get_object_or_404(Course, pk=request.session["course_id"])

        CoursePermissions.require_course_staff(request.user, course.id)

        render_dict = dict()
        render_dict["course"] = course
        render_dict["cid"] = course.id

        MCItemInlineFormSet = inlineformset_factory(
            RubricQuestion,
            RubricQuestionMultipleChoiceItem,
            form=RubricQuestionMultipleChoiceForm,
            fields=("text", "marks"),
            extra=2,
        )

        if request.GET.get("popup", False):
            render_dict["remove_navbar"] = True
            render_dict["is_popup"] = True

        questionForm = RubricQuestionForm(data=request.POST or None)
        if questionForm.is_valid():
            question = questionForm.save(commit=False)

            formset = MCItemInlineFormSet(request.POST, instance=question)
            if formset.is_valid():
                question.save()
                formset.save()
                if "popup" in request.POST:
                    return PopupUtils.return_to_parent(
                        question._get_pk_val(), question, ReviewHelper.preview(question)
                    )
                else:
                    return HttpResponseRedirect("/review/rubric/question/list/")
            else:
                messages.error(request, formset.errors)

        else:
            messages.error(request, questionForm.errors)
            formset = MCItemInlineFormSet()

        render_dict["form"] = questionForm
        render_dict["mcitem_formset"] = formset

        return render(request, "rubric-question-create.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def rubric_question_edit(request, qid):
        "Edit a rubric question"
        # TODO: permission?
        # TODO: there's no way to access this from UI

        course = get_object_or_404(Course, pk=request.session["course_id"])
        CoursePermissions.require_course_staff(request.user, course.id)

        render_dict = dict()

        question = get_object_or_404(RubricQuestion, pk=qid)
        # items = question.choices.all()
        MCItemInlineFormSet = inlineformset_factory(
            RubricQuestion,
            RubricQuestionMultipleChoiceItem,
            form=RubricQuestionMultipleChoiceForm,
            fields=("text", "marks"),
            extra=0,
        )

        questionForm = RubricQuestionForm(data=request.POST or None, instance=question)
        formset = MCItemInlineFormSet(data=request.POST or None, instance=question)

        render_dict["question"] = question
        render_dict["form"] = questionForm
        render_dict["mcitem_formset"] = formset

        if questionForm.is_valid():
            question = questionForm.save(commit=False)

            if formset.is_valid():
                question.save()
                formset.save()
                return HttpResponseRedirect("/review/rubric/question/list/")
            else:
                messages.error(request, formset.errors)

        else:
            messages.error(request, questionForm.errors)
            return render(request, "rubric-question-edit.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def rubric_question_delete(request, qid):
        "Delete a rubric question"

        course = get_object_or_404(Course, pk=request.session["course_id"])
        CoursePermissions.require_course_staff(request.user, course.id)

        render_dict = dict()

        question = get_object_or_404(RubricQuestion, pk=qid)

        if question.safe_to_remove():
            question.delete()
            messages.info(request, "Rubric question removed successfully.")
        else:
            messages.warning(
                request,
                "Could not remove rubric question (probably already used in a review).",
            )

        return HttpResponseRedirect(reverse("review:rubric_question_list"))

    @staticmethod
    @login_required
    @chosen_course_required
    def rubric_question_list(request):
        "Show the list of rubric questions"

        course = get_object_or_404(Course, pk=request.session["course_id"])
        CoursePermissions.require_course_staff(request.user, course.id)

        render_dict = dict()
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        # We probably do not this for now but we'd keep it here
        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict["course"] = course
        render_dict["cid"] = course.id

        render_dict["questions"] = RubricQuestion._default_manager.all()
        return render(request, "rubric-question-list.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def manage_review_settings(request, aid):
        "Create/edit review settings"

        render_dict = dict()

        # TODO: this shouldn't be here!!
        # We probably do not this for now but we'd keep it here
        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict["course"] = course
        render_dict["cid"] = course.id

        CoursePermissions.require_instructor(request.user, course.id)

        assignment = get_object_or_404(Assignment, pk=aid)
        render_dict["assignment"] = assignment
        awr = assignment_with_reviews = AssignmentWithReviews._default_manager.filter(
            pk=aid
        ).first()

        form = AssignmentWithReviewsForm(
            data=request.POST or None, assignment=assignment, instance=awr
        )

        render_dict["form"] = form

        if form.is_valid():
            awr = form.save(commit=False)
            eventLogger.info(
                "Creating/editing review settings [aid: %s] (by %s): %s"
                % (str(aid), request.user.username, str(request.POST))
            )
            assignment.populate_max_grade()
            assignment.save()
            return HttpResponseRedirect(reverse("assignment:list_for_course"))

        render_dict["model_name"] = "review"
        return render(request, "review-settings.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def assignment_review_list(request, aid):
        "A complete list of reviews per submission"

        assignment = get_object_or_404(Assignment, pk=aid)
        course = get_object_or_404(Course, pk=request.session["course_id"])

        CoursePermissions.require_course_staff(request.user, assignment.course.id)

        render_dict = dict()
        render_dict["assignment"] = assignment

        if not course.can_tas_see_reviews and CourseBase.is_ta(
            request.user, assignment.course.id
        ):
            render_dict["anonymize_st_reviews"] = True

        search_term = request.GET.get("search", "")

        page_num = ReviewUtils.get_numeral_value(request.GET, "page", 1)
        per_page = ReviewUtils.get_numeral_value(request.GET, "per_page", 10)

        submissions = assignment.assignmentsubmission_set.prefetch_related(
            "reviewassignment_set",
            "reviewassignment_set__grader",
            "reviewassignment_set__question",
            "reviewassignment_set__grader__user",
        )
        if search_term:
            submissions = submissions.filter(
                Q(author__user__first_name__icontains=search_term)
                | Q(author__user__last_name__icontains=search_term)
                | Q(author__user__username__icontains=search_term)
            )

        paginator = Paginator(
            submissions.order_by(
                "author__user__last_name",
                "author__user__first_name",
                "author__user__username",
            ),
            per_page,
        )

        try:
            submissions = paginator.page(page_num)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            submissions = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            submissions = paginator.page(paginator.num_pages)

        render_dict["submissions_page"] = submissions
        render_dict["per_page"] = str(per_page)
        render_dict["page_range"] = paginator.page_range
        render_dict["submissions_count"] = paginator.count
        render_dict["search_term"] = search_term

        return render(
            request, "review-complete-assignment-review-list.html", render_dict
        )

    @staticmethod
    @login_required
    @chosen_course_required
    def assign_self_reviews(request, cid):
        "Create self review assignments"

        render_dict = dict()
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        # We probably do not this for now but we'd keep it here
        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict["course"] = course
        render_dict["cid"] = course.id

        render_dict["cid"] = cid

        assignments = Assignment._default_manager.filter(course__id=cid)
        render_dict["assignments"] = assignments

        rubrics = Rubric._default_manager.all()
        render_dict["rubrics"] = rubrics

        if request.method == "POST":

            assignment_id = request.POST.get("assignment", None)

            deadline_date = request.POST.get("deadline_date", None)
            deadline_time = request.POST.get("deadline_time", None)
            datetime_string = "%s %s" % (deadline_date, deadline_time)
            deadline = datetime.strptime(datetime_string, "%Y-%m-%d %H:%M")

            # TODO: check if we need this
            rubric_id = request.POST.get("rubric", None)

            if assignment_id != None:
                ReviewBase.assign_self_reviews(assignment_id, rubric_id)

            return HttpResponseRedirect("/review/list_for_course/")

        return render(request, "review-assign-self-reviews.html", render_dict)

    @staticmethod
    @login_required
    @review_settings_required
    def request_review_submission(request, sid):
        "Request to be assigned a review for a specific submission (requires staff)"

        submission = get_object_or_404(AssignmentSubmission, pk=sid)
        CoursePermissions.require_course_staff(
            request.user, submission.assignment.course.id
        )

        review = submission.reviewassignment_set.filter(
            grader__user=request.user
        ).first()

        if review is not None:
            messages.warning(request, "Review already exists")
            return HttpResponseRedirect(reverse("review:view", args={review.id}))
        else:
            review = ReviewAssignment._default_manager.create(
                submission=submission,
                grader=CourseBase.get_course_member(
                    request.user, submission.assignment.course.id
                ),
            )
            return HttpResponseRedirect(reverse("review:review_edit", args={review.id}))

    @staticmethod
    @login_required
    @review_settings_required
    def assign_spot_checks(request, aid):
        "Assign TA reviews"

        assignment = get_object_or_404(Assignment, pk=aid)
        awr = assignment.assignmentwithreviews

        CoursePermissions.require_course_staff(request.user, assignment.course.id)

        render_dict = dict()
        render_dict["model_name"] = "review"
        render_dict["assignment"] = assignment
        render_dict["cid"] = assignment.course.id

        if awr.ta_reviews_per_question:
            form = AssignTAGradingForm(request.POST or None, assignment=assignment)
        else:
            form = AssignTAReviewsForm(request.POST or None, assignment=assignment)

        render_dict["form"] = form

        if form.fields["num_to_assign"].max_value < 1:
            messages.warning(
                request, "All submissions already have TAs assigned to review them."
            )
            return HttpResponseRedirect(reverse("review:list_for_course"))

        if form.is_valid():
            assigned = ReviewBase.assign_spot_checks(
                aid,
                form.cleaned_data["num_to_assign"],
                form.get_all_tas(),
                awr.ta_reviews_per_question,
                form.evaluate_student_reviews(),
            )
            messages.success(request, "Successfully assigned %d TA reviews." % assigned)
            return HttpResponseRedirect(reverse("review:list_for_course"))

        return render(request, "review-assign-spot-checks.html", render_dict)


    @staticmethod
    @login_required
    @review_settings_required
    def upload_spot_checks(request, aid):

        assignment = get_object_or_404(Assignment, pk=aid)
        awr = assignment.assignmentwithreviews

        CoursePermissions.require_course_staff(request.user, assignment.course.id)

        render_dict = dict()
        render_dict["model_name"] = "review"
        render_dict["assignment"] = assignment
        render_dict["cid"] = assignment.course.id

        if request.method == 'POST':
            form = UploadTAGradingForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['file']
                # let's check if it is a csv file
                if not csv_file.name.endswith('.csv'):
                    messages.error(request, 'This is not a CSV file.')
                else:
                    count= ReviewBase.upload_spot_checks(csv_file)
                    messages.success(request, "Successfully assigned %d TA reviews." % count)
                    return HttpResponseRedirect(reverse("review:list_for_course"))


        if awr.ta_reviews_per_question:
            form = UploadTAGradingForm()
        else:
            form = UploadTAGradingForm()

        render_dict["form"] = form



        return render(request, "review-upload-spot-checks.html", render_dict)

    @staticmethod
    @login_required
    @review_settings_required
    def upload_spot_checking_priorities(request, aid):

        assignment = get_object_or_404(Assignment, pk=aid)
        awr = assignment.assignmentwithreviews

        CoursePermissions.require_course_staff(request.user, assignment.course.id)

        render_dict = dict()
        render_dict["model_name"] = "review"
        render_dict["assignment"] = assignment
        render_dict["cid"] = assignment.course.id

        if request.method == 'POST':
            form = UploadSpotcheckingPriorityForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['file']
                # let's check if it is a csv file
                if not csv_file.name.endswith('.csv'):
                    messages.error(request, 'This is not a CSV file.')
                else:
                    count= ReviewBase.upload_spot_checking_priorities(csv_file)
                    messages.success(request, "Successfully assigned %d Spot checking priorities to submissions." % count)
                    return HttpResponseRedirect(reverse("review:list_for_course"))



        form = UploadSpotcheckingPriorityForm()


        render_dict["form"] = form



        return render(request, "review-upload-spot-checking-priorities.html", render_dict)


    @staticmethod
    @login_required
    @chosen_course_required
    @review_settings_required
    def assign_student_reviews(request, aid):
        """
        Assign student reviews

        The functionality differs based on `assignment.course.enable_independent_pool`
        """

        assignment = Assignment._default_manager.get(pk=aid)
        render_dict = dict()

        render_dict["assignment"] = assignment
        render_dict["cid"] = assignment.course.id

        rubrics = Rubric._default_manager.all()
        render_dict["rubrics"] = rubrics
        render_dict["model_name"] = "review"

        render_dict["form"] = form = AssignStudentReviewsForm(
            request.POST or None, assignment=assignment
        )

        if form.is_valid():
            ReviewBase.assign_student_reviews(aid, **form.cleaned_data)
            return HttpResponseRedirect("/review/list_for_course/")

        return render(request, "review-assign-student-reviews.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    @review_settings_required
    def upload_student_reviews(request, aid):
        """
        Upload student reviews

        """

        assignment = Assignment._default_manager.get(pk=aid)
        render_dict = dict()

        render_dict["assignment"] = assignment
        render_dict["cid"] = assignment.course.id

        rubrics = Rubric._default_manager.all()
        render_dict["rubrics"] = rubrics
        render_dict["model_name"] = "review"

        if request.method == 'POST':
            form = UploadStudentReviewsForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['file']
                # let's check if it is a csv file
                if not csv_file.name.endswith('.csv'):
                    messages.error(request, 'This is not a CSV file.')
                else:
                    count= ReviewBase.upload_student_reviews(csv_file)
                    messages.success(request, "Successfully assigned %d Student reviews." % count)
                    return HttpResponseRedirect(reverse("review:list_for_course"))

        
        form = UploadStudentReviewsForm()

        render_dict["form"] = form
        return render(request, "review-upload-student-reviews.html", render_dict)

    @staticmethod
    @login_required
    def request_random_review(request, aid):
        "Assign a random review to the TA"

        awr = None
        if not AssignmentWithReviews._default_manager.filter(pk=aid).exists():
            messages.error(
                request,
                "A deadline for TA review hasn't been set.  Please ask your instructor to set a deadline before requesting a review.",
            )
            return HttpResponseRedirect("/review/my_reviews_of_other_submissions")
        else:
            awr = AssignmentWithReviews._default_manager.get(pk=aid)

        sub_queryset = ReviewBase.find_available_submissions(request.user, aid)
        if not sub_queryset.exists():
            messages.error(
                request,
                "There is no more submission to review for assignment %s.  All submissions have been assigned to be reviewed by a TA."
                % awr.assignment.name,
            )
            return HttpResponseRedirect("/review/my_reviews_of_other_submissions/")

        # Choose a random submission
        sub = ReviewBase.get_random_object(sub_queryset)

        # Let's create a new ReviewAssignment
        rev = ReviewAssignment(
            submission=sub,
            grader__user=request.user,
            rubric=awr.rubric_default,
            deadline=awr.ta_review_deadline_default,
        )
        rev.save()
        # # .. and redirect the user to the review page
        # return HttpResponseRedirect('/review/%d/create/' % rev.id)

        return HttpResponseRedirect("/review/my_reviews_of_other_submissions/")


    @staticmethod
    def next_request_helper(sub_queryset, request, cid):
        grader=CourseBase.get_course_member(request.user, cid)
        for sub in sub_queryset:
            if Appeal._default_manager.filter(submission=sub).exists():
                appeals = Appeal._default_manager.filter(submission=sub)
                appeal= appeals[0]
                if appeal.assignee.role == 'instructor' :
                    appeal.assignee = grader
                    appeal.save()
                    render_dict = dict()
                    render_dict["appeal"] = appeal
                    render_dict["appeal_data"] = [("Request", appeal.request or "[empty]")]
                    extra_data = [
                        ("Status", appeal.get_status_display()),
                        ("Response", appeal.response or "[Not available]"),
                    ]
                    if appeal.can_be_modified():
                        render_dict["appeal_form"] = AppealForm(instance=appeal)
                    else:
                        render_dict["appeal_data"] += extra_data
                    render_dict["submission"] = appeal.submission
                    render_dict["reviews"] = appeal.submission.reviewassignment_set.all()
                    render_dict["is_assignee"] = appeal.assignee.user == request.user
                    sub.spotchecking_priority= 1001
                    sub.save()
                    return render(request, "appeal-view.html", render_dict)


            if not ReviewAssignment._default_manager.filter(submission=sub, grader__role="ta").exists():
                rev = ReviewAssignment._default_manager.create(
                    submission= sub,
                    grader= grader
                )
                EvaluationBase._assign_evaluation_on_spot_check(sub, rev)
                sub.spotchecking_priority= 1001
                sub.save()
        # # .. and redirect the user to the review page
                print ("successful!")
                return HttpResponseRedirect('/review/%d/create/' % rev.id) 

        messages.error(
            request,
            "There is no more submission to review for this course."
        )
        return HttpResponseRedirect(reverse("home:home"))    



    @staticmethod
    @login_required
    def request_next_review(request ,cid):
        "Assign a random review to the TA"

        if not AssignmentWithReviews._default_manager.filter(assignment__course__id=cid).exists():
            messages.error(
                request,
                "A deadline for TA review hasn't been set.  Please ask your instructor to set a deadline before requesting a review.",
            )
            return HttpResponseRedirect(reverse("home:home"))

        sub_queryset = ( AssignmentSubmission._default_manager.filter(assignment__course__id=cid, calibration_id=0)
            .exclude(assignment__assignment_type='quiz')
            .order_by('spotchecking_priority')
        )
        if not sub_queryset.exists():
            messages.error(
                request,
                "There is no more submission to review for this course.  All submissions have been assigned to be reviewed by a TA."
            )
            return HttpResponseRedirect(reverse("home:home"))
        else:
#            print (sub_queryset[0].spotchecking_priority)
            return ReviewViews.next_request_helper(sub_queryset,request, cid)




    
#            rev = ReviewAssignment(
#            submission=sub,
#            grader__user=request.user,
#            rubric=awr.rubric_default,
#            deadline=awr.ta_review_deadline_default,
#            )
#            rev.save()

                

        # Choose a random submission
#        sub = ReviewBase.get_random_object(sub_queryset)

        # Let's create a new ReviewAssignment

        # # .. and redirect the user to the review page
        # return HttpResponseRedirect('/review/%d/create/' % rev.id)
        messages.error(
            request,
                "There is no more submission to review for this course.  All submissions have been assigned to be reviewed by a TA."
        )
        return HttpResponseRedirect(reverse("home:home"))

    @staticmethod
    @login_required
    @chosen_course_required
    def review_create(request, rid):

        render_dict = dict()
        render_dict["model_name"] = "review"
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        review_assignment = get_object_or_404(ReviewAssignment, pk=rid)
        render_dict["model"] = review_assignment

        if review_assignment.grader.role == 'ta':
            participations = CourseParticipation.objects.filter(participant = review_assignment.grader).order_by('-id')
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

        # if review_assignment.submission.calibration_id == 0 and not review_assignment.grader.qualified:
        #     messages.warning(
        #         request,
        #         "You are not yet qualified. You need to complete the quiz or contact the course staff to get qualified.",
        #     )
        #     return HttpResponseRedirect(reverse("home:home"))

        if ReviewContent._default_manager.filter(
            review_assignment=review_assignment
        ).exists():
            if review_assignment.submission.calibration_id == 0:
                return HttpResponseRedirect("/review/%s/view/" % rid)
            else:
                messages.error(
                    request, "You have already submitted a review for this calibration essay. Please try a new one."
                )
                return HttpResponseRedirect("/calibration/%s/view/" % rid)

        if review_assignment.grader.user != request.user:
            if not review_assignment.evaluations.filter(
                grader__user=request.user
            ).exists():
                CoursePermissions.require_course_staff(
                    request.user, review_assignment.submission.assignment.course.id
                )
        # elif review_assignment.grader.active == False:
        #     messages.warning(request, 'This account has been deactivated, please contact course staff')
        #     return HttpResponseRedirect(reverse('home:home'))

        # elif (not review_assignment.grader.is_independent and review_assignment.submission.calibration_id ==0):
        #    messages.warning(request, 'You are not an independent grader yet, please do the calibration essays first!')
        #    return HttpResponseRedirect(reverse('home:home'))
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict["course"] = course
        render_dict["cid"] = course.id

        if review_assignment.question is not None:
            render_dict["questions"] = [review_assignment.question.id]
        else:
            render_dict["questions"] = None

        if review_assignment.grader.role != "student":
            render_dict["members"] = course.members.filter(
                Q(role="ta") | Q(role="instructor")
            )

        rcform = ReviewContentForm(
            request.POST or None, request.FILES or None, instance=review_assignment
        )
        render_dict["form"] = rcform

        if rcform.is_valid():
            rcform.save()
            # ReviewBase.save_review_files(rcform.cleaned_data,
            #     review_assignment, request)
            if review_assignment.submission.calibration_id == 0:
                if review_assignment.grader.role == 'ta':
                    student_reviews = ReviewAssignment.objects.filter(submission = review_assignment.submission, grader__role = 'student')
                    for student_review in student_reviews:
                        student_review.markingload = 0
                        student_review.save()
                return HttpResponseRedirect("/review/%s/view/" % rid)
            else:
                gr = CourseBase.get_course_member(request.user, course.id)
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
#                if not gr.is_independent and gr.is_independent != CalibrationBase.check_if_independent(gr, course):
#                    gr.is_independent = CalibrationBase.check_if_independent(gr, course)
#                    gr.time_is_independent_changed = timezone.now()
#                    gr.save()
                return HttpResponseRedirect("/calibration/%s/view/" % rid)

        else:
            # TODO: messages.error(request, rcform.errors)
            render_dict["is_create"] = True
            return render(request, "review-create.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def review_view(request, rid):

        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict = dict()
        render_dict["model_name"] = "review"
        render_dict["edit_link"] = "review:review_edit"

        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        review = get_object_or_404(ReviewAssignment, pk=rid)
        render_dict["model"] = review
        render_dict["is_author"] = request.user == review.grader.user
#        render_dict["is_grader"] = False

        # TODO: give access to the submission author too, maybe?

        if (
            not render_dict["is_author"]
            and not request.user.is_superuser
            and not review.evaluations.filter(grader__user=request.user).exists()
            and not ReviewAssignment._default_manager.filter(submission= review.submission, grader__user= request.user).exists()
        ):
            if review.submission.author.user == request.user:
                if review.submitted == False:
                    raise PermissionDenied(
                        "You cannot see the reviews of your submissions, until they are submitted."
                    )
            elif ReviewAssignment._default_manager.filter(submission= review.submission, grader__user= request.user).exists():
                if review.submitted == False:
                    raise PermissionDenied(
                        "You cannot see the reviews of this submissions, until they are submitted."
                    )   
            else:
                # It's not the submission author nor the grader, then it must be one of staff
                if (
                    (course.can_tas_see_reviews and review.grader.role == "student")
                    or Appeal._default_manager.filter(
                        submission=review.submission
                    ).exists()
                ):
                    permission_req = CoursePermissions.require_course_staff
                else:
                    permission_req = CoursePermissions.require_instructor

                permission_req(request.user, review.submission.assignment.course.id)

        if (
            ReviewAssignment._default_manager.filter(submission= review.submission, grader__user= request.user).exists() 
            and review.grader.role == 'ta' 
            and review.submission.calibration_id != 0
        ):
            raise PermissionDenied(
                    "You cannot see this review."
                )    
                    
        render_dict[
            "related_evaluations"
        ] = related_eval = EvaluationAssignment._default_manager.filter(
            review__submission=review.submission, grader__user=request.user
        )
        render_dict["related_evaluations_incomplete"] = related_eval.filter(
            submitted=False
        ).exists()

        render_dict["can_be_evaluated"] = not related_eval.filter(
            review=review
        ).exists() and (review.grader.role == "student")

        render_dict["can_report"] = (
            not render_dict["is_author"]
            and review.grader.role == "student"
            and not InaptFlag._default_manager.filter(review=review).exists()
            and not InaptReport._default_manager.filter(
                review=review, reporter__role="student"
            ).exists()
        )

        if review.question is not None:
            render_dict["questions"] = [review.question.id]
        else:
            render_dict["questions"] = None

        render_dict["components"] = ReviewBase.get_review_components_dict(review)

        return render(request, "review-view.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def reason_viewed(request, content_id):
        content = ReviewContent._default_manager.filter(id = content_id)
        ct= content[0]
        ct.is_reason_viewed= True
        ct.save()
        return HttpResponse('the reason has been viewed')

    @staticmethod
    @login_required
    @chosen_course_required
    def endorse(request, rid):
        review = ReviewAssignment._default_manager.filter(id = rid)
        rv= review[0]
        rv.endorsed= True
        rv.save()
        return HttpResponse('the review has been endorsed')
    
    
    
    @staticmethod
    @login_required
    @chosen_course_required
    def review_edit(request, rid):

        render_dict = dict()
        render_dict["model_name"] = "review"
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        review_assignment = ReviewAssignment._default_manager.get(pk=rid)
        render_dict["model"] = review_assignment

        # if review_assignment.submission.calibration_id == 0 and not review_assignment.grader.qualified:
        #     messages.warning(
        #         request,
        #         "You are not yet qualified. You need to complete the quiz or contact the course staff to get qualified.",
        #     )
        #     return HttpResponseRedirect(reverse("home:home"))

        if review_assignment.grader.user != request.user:
            return HttpResponseForbidden("Only the grader can edit a review assignment")
        elif review_assignment.grader.active == False:
            return HttpResponseForbidden(
                "This account has been deactivated, please contact course staff"
            )
        elif review_assignment.submission.calibration_id != 0:
            # student's can't edit their calibration reviews since they have already seen the answers
            # the course staff on the other hand can for creating calibration ground truth reviews
            if not CourseBase.is_course_staff(
                request.user, review_assignment.submission.assignment.course.id
            ):
                return HttpResponseForbidden("You can not edit a calibration review")

        if review_assignment.question is not None:
            render_dict["questions"] = [review_assignment.question.id]
        else:
            render_dict["questions"] = None

        rcform = ReviewContentForm(
            request.POST or None, request.FILES or None, instance=review_assignment
        )
        render_dict["form"] = rcform

        if rcform.is_valid():
            has_file = rcform.save()

            # Remove the previous files
            # ReviewBase.remove_review_files(review_assignment)

            # Add the new ones
            # ReviewBase.save_review_files(rcform.cleaned_data, review_assignment, request)

            return HttpResponseRedirect("/review/%s/view/" % rid)
        else:
            # TODO: messages.error(request, rcform.errors)
            render_dict["is_create"] = False
            return render(request, "review-create.html", render_dict)

    @staticmethod
    @login_required
    def review_reassign(request, rid):
        review_assignment = ReviewAssignment._default_manager.get(pk=rid)

        course = review_assignment.submission.assignment.course

        CoursePermissions.require_course_staff(request.user, course.id)

        if review_assignment.grader.user != request.user:
            return HttpResponseForbidden(
                "Only the grader can create a review assignment."
            )

        if request.method == "POST":
            member = CourseMember._default_manager.filter(
                id=request.POST.get("member", -1)
            ).first()
            if member is None:
                messages.error(request, "No user selected.")
            elif member.course != course:
                messages.error(
                    request, "The selected user is not a member of this course."
                )
            else:
                review_assignment.grader = member
                review_assignment.save()
                eventLogger.warning(
                    "Reassigned [rid: %s] from %s (%d) to %s (%d)"
                    % (
                        str(rid),
                        request.user.username,
                        request.user.id,
                        member.user.username,
                        member.user.id,
                    )
                )
                messages.info(request, "New grader assigned for review.")

            return HttpResponseRedirect(reverse("home:home"))
        else:
            return HttpResponseForbidden()

    @staticmethod
    @login_required
    def assignment_create(request, cid):
        "Create a review assignment - not used right now"

        render_dict = dict()
        # render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        course = Course._default_manager.get(pk=cid)
        assignments = Assignment._default_manager.filter(course__id=cid)
        render_dict["assignments"] = assignments

        if request.method == "POST":
            form = ReviewAssignmentForm(data=request.POST)
            if form.is_valid():
                form.save()
                return HttpResponseRedirect("/review/list_for_course/")
            else:
                messages.error(request, form.errors)
        else:
            form = ReviewAssignmentForm()
            form.fields[
                "submission"
            ].queryset = AssignmentSubmission._default_manager.filter(
                assignment__course__id=cid
            )

        render_dict["reviewAssignForm"] = form
        render_dict["course"] = course
        return render(request, "review-assignment-create.html", render_dict)

    @staticmethod
    @login_required
    def list(request):
        "List all review assignments - not used right now"

        info = dict()

        if request.user.is_superuser:
            # All the courses since I am the admin.
            courses = Course._default_manager.all().order_by("displayname")

            for course in courses:

                info[course.displayname] = dict()
                info[course.displayname]["course"] = course

                reviews = ReviewAssignment._default_manager.filter(
                    submission__assignment__course=course
                ).order_by("submission__assignment__name")
                info[course.displayname]["reviews"] = reviews

                # TAs
                tas = course.members.filter(coursemember__role="ta")
                info[course.displayname]["tas"] = tas

                # Instructors
                instructors = course.members.filter(coursemember__role="instructor")
                info[course.displayname]["instructors"] = instructors

                reviews_assigned_to_me = reviews.filter(grader__user=request.user)
                info[course.displayname][
                    "reviews_assigned_to_me"
                ] = reviews_assigned_to_me

        else:

            # All the courses I am associated with
            courses = CourseBase.get_courses(request.user).order_by("displayname")

            for course in courses:

                info[course.displayname] = dict()
                info[course.displayname]["course"] = course

                # All the reviews for this course
                reviews = ReviewAssignment._default_manager.filter(
                    submission__assignment__course=course
                ).order_by("submission__assignment__name")
                info[course.displayname]["reviews"] = reviews

                tas = course.members.filter(coursemember__role="ta")
                info[course.displayname]["tas"] = tas

                instructors = course.members.filter(coursemember__role="instructor")
                info[course.displayname]["instructors"] = instructors

                # Reviews assigned to me
                reviews_assigned_to_me = reviews.filter(grader__user=request.user)
                info[course.displayname][
                    "reviews_assigned_to_me"
                ] = reviews_assigned_to_me

                role = CourseMember._default_manager.get(
                    user=request.user, course=course
                ).role
                reviewsOfMySubmissions = None
                if role == "student":
                    # Reviews of my submissions
                    reviewsOfMySubmissions = reviews.filter(
                        submission__author__user=request.user
                    )
                info[course.displayname][
                    "reviewsOfMySubmissions"
                ] = reviewsOfMySubmissions

                info[course.displayname]["is_student"] = CourseBase.is_student(
                    request.user, course.id
                )
                info[course.displayname]["is_ta"] = CourseBase.is_ta(
                    request.user, course.id
                )
                info[course.displayname]["is_instructor"] = CourseBase.is_instructor(
                    request.user, course.id
                )

        render_dict = dict()
        render_dict["info"] = sorted(info.items())

        # if request.user.is_superuser:
        #     render_dict['courses'] = Course._default_manager.all().order_by('displayname')
        # else:
        #   render_dict['courses'] = CourseBase.get_courses(request.user).order_by('displayname')

        return render(request, "review-list.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def list_priorities(request):
        "List all spotchecking priorities for the course."

        course = get_object_or_404(Course, pk=request.session["course_id"])    
        cm = CourseBase.get_course_member(request.user, course.id)
        if not request.user.is_superuser:
            if cm.role == 'student':
                return HttpResponseRedirect(reverse("review:my_reviews"))

        # Count number of assignments at each priority
        priorities_db = (AssignmentSubmission._default_manager.filter(assignment__course=course)
            .values('spotchecking_priority')
            .annotate(Count('spotchecking_priority'))
        )
        priority_lookup = [{
            'priority': d['spotchecking_priority'], 
            'count': d['spotchecking_priority__count']
        } for d in priorities_db]

        # Find first 10 assignments at each priority
        for i in range(len(priority_lookup)): 
            priority = priority_lookup[i]['priority']
            first_submissions = (AssignmentSubmission._default_manager
                .filter(assignment__course=course, spotchecking_priority=priority)[:10]
            )
            priority_lookup[i]['submissions'] = first_submissions

        # Render
        render_dict = {
            'priorities': priority_lookup
        }
        return render(request, "review-list-priorities.html", render_dict)