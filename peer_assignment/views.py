import collections
import logging
import json
import copy
import os

from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.forms.models import model_to_dict
from django.forms import inlineformset_factory
from django.http import HttpResponseRedirect, JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q
from django.db import IntegrityError
from django.shortcuts import render as djangoRender

from peer_home.wrappers import render

from peer_course.models import Course, CourseMember
from peer_course.decorators import chosen_course_required

from .models import *
from .forms import *
from .serializers import AssignmentSerializer
from peer_review.choices import PDF
from peer_review.models import AssignmentWithReviews
from peer_review.models import ReviewAssignment
from peer_course.base import CourseBase, CoursePermissions
from .base import AssignmentBase, question_creators
from django.views.decorators.csrf import csrf_exempt

eventLogger = logging.getLogger("mta.events")
debugLogger = logging.getLogger("mta.debug")

# Create your views here.

# TODO (master): use easier 6 vs 9 LoC form views
# TODO (master): get_object_or_404(Model, pk=pk)
# TODO (master): tests!
# TODO (master): need a 404 not found page


class AssignmentViews:
    @staticmethod
    @chosen_course_required
    @login_required
    def list_for_course(request):
        "[About to become deprecated] Display all the assignments for the chosen course"
        course = get_object_or_404(Course, pk=request.session["course_id"])
        is_staff = CourseBase.is_course_staff(request.user, course.id)
        # if not is_staff:
        #     return HttpResponseRedirect(reverse('home:home'))
        # TODO (farzad): Ask why?
        # TODO: only show edit submission button if not past deadline

        # TODO: use this instead: AssignmentBase.get_user_assignments_by_status(request.user),

        render_dict = dict()

        course = Course._default_manager.get(pk=request.session["course_id"])
        render_dict["course"] = course
        render_dict["cid"] = course.id

        assignments_all = (
            Assignment._default_manager.filter(course=course)
            .extra(select={"deadline_null": "deadline is null"})
            .order_by("-deadline_null", "-deadline")
        )
        # this if statement is redundant right now, but not removing it, since things might change
        if not is_staff:
            assignments_all = assignments_all.filter(browsable=True)
        render_dict["assignments"] = assignments_all
        assignments_completed = assignments_all.filter(
            assignmentsubmission__author__user=request.user
        )
        assignments_pending = assignments_all.exclude(
            id__in=assignments_completed
        ).filter(deadline__gte=timezone.now())
        render_dict["assignments_pending"] = assignments_pending

        return render(request, "assignment-list-for-course.html", render_dict)

    @staticmethod
    @chosen_course_required
    @login_required
    def view(request, aid):
        "Display a particular assignment"

        # render_dict['courses'] = request.user.course_set.all().order_by('displayname')
        render_dict = dict()
        assignment = get_object_or_404(Assignment, pk=aid)

        if assignment.browsable is False:
            CoursePermissions.require_course_staff(request.user, assignment.course.id)
            # messages.warning(request, 'This assignment has not been made Visible')
            # return HttpResponseRedirect(reverse('assignment:list_for_course'))

        CoursePermissions.require_course_member(request.user, assignment.course.id)
        # TODO: students can only view assigned reviews ....

        # What's happening here?
        # render_dict['courses'] = CourseBase.get_courses(request.user)
        # TODO: fix this later.order_by('displayname')

        # if not 'cid' in request.session:
        #    return render(request, 'assignment-view.html', render_dict)

        # cid = request.session['cid']
        # course = Course._default_manager.get(pk=cid)
        # course = Course._default_manager.get(pk=request.session['course_id'])
        # render_dict['course'] = course
        # render_dict['cid'] = course.id

        render_dict["questions"] = assignment.questions.all()
        render_dict["assignment"] = assignment
        render_dict["my_submission"] = assignment.assignmentsubmission_set.filter(
            author__user=request.user
        ).first()
        return render(request, "assignment-view.html", render_dict)

    @staticmethod
    @chosen_course_required
    @login_required
    def create(request):
        "Create an assignment"
        # TODO: handle free-form
        course = get_object_or_404(Course, pk=request.session["course_id"])

        CoursePermissions.require_course_staff(request.user, course.id)

        redirect_address = reverse("assignment:list_for_course")

        if request.method == "POST":
            return AssignmentViews._handle_assignment_request(
                request, course, success_redirect_addr=redirect_address
            )
        else:
            render_dict = dict()
            render_dict["data"] = None
            render_dict[
                "data_json"
            ] = '{"num_questions": 1, "max_late_units": 2, "grace_hours": 2, "qualification_grade": 10000}'
            render_dict["is_create"] = True
            render_dict["course"] = course
            render_dict["redirect_address"] = redirect_address
            return render(request, "assignment-create2.html", render_dict)

    @staticmethod
    def _handle_assignment_request(
        request, course, success_redirect_addr, instance=None
    ):
        data = dict(
            [(k, v) for k, v in request.POST.items() if v != "" and k != "statement"]
        )
        data["course"] = course.id
        if "statement" in request.FILES:
            data["statement"] = request.FILES["statement"]
        serializer = AssignmentSerializer(instance, data=data)
        if serializer.is_valid():
            saved_instance = serializer.save()
            eventLogger.info(
                "Creating/editing assignment [aid: %s]" % str(saved_instance.id)
            )
            # print(saved_instance)
            if saved_instance.assignment_type != data["assignment_type"]:
                debugLogger.log(
                    "Assignment type changed, removing all previous questions"
                )
                saved_instance.questions.all().delete()
            # TODO: handle errors?
            q_creator = question_creators[data["assignment_type"]]
            q_creator(saved_instance, data)
        else:
            # print(serializer.errors)
            # raise Exception(serializer.errors)
            # TODO: fix this!
            # print('errors:', serializer.errors)
            return JsonResponse(serializer.errors, status=400)
        return HttpResponseRedirect(success_redirect_addr)

    @staticmethod
    @chosen_course_required
    @login_required
    def edit(request, aid):
        "Edit an assignment"
        # TODO: handle free-form type
        # TODO: permissions?
        assignment = get_object_or_404(Assignment, pk=aid)
        redirect_address = reverse("assignment:view", kwargs={"aid": aid})

        CoursePermissions.require_course_staff(request.user, assignment.course.id)

        if request.method == "POST":
            return AssignmentViews._handle_assignment_request(
                request,
                assignment.course,
                instance=assignment,
                success_redirect_addr=redirect_address,
            )

        serializer = AssignmentSerializer(assignment)
        render_dict = dict()
        render_dict["is_create"] = False
        render_dict["data"] = serializer.data
        if assignment.assignment_type != PDF:
            render_dict["data"]["questions"] = [
                {
                    "pk": q.pk,
                    "title": q.title,
                    "description": q.description,
                    "choices": [
                        {"pk": c.pk, "choice_text": c.choice_text, "marks": c.marks}
                        for c in q.choices.all()
                    ],
                }
                for q in assignment.questions.all()
            ]
        render_dict["data_json"] = (
            json.dumps(render_dict["data"]).replace("\\", "\\\\").replace("'", "\\'")
        )
        render_dict["course"] = assignment.course
        render_dict["redirect_address"] = redirect_address
        return render(request, "assignment-create2.html", render_dict)

    @staticmethod
    @login_required
    def show(request, aid):
        "Show the assignment"
        assignment = get_object_or_404(Assignment, id=aid)
        CoursePermissions.require_course_staff(request.user, assignment.course.id)
        if assignment.deadline is not None or not assignment.submission_required:
            assignment.browsable = True
            assignment.save()
        else:
            messages.warning(
                request,
                "Please set assignment deadline before making it visible to students.",
            )
        eventLogger.info("Showing assignment [aid: %s]" % str(aid))
        # TODO: show error if condition not met
        return HttpResponseRedirect(reverse("assignment:list_for_course"))

    @staticmethod
    @login_required
    def hide(request, aid):
        "Hide the assignment"

        assignment = get_object_or_404(Assignment, id=aid)
        CoursePermissions.require_course_staff(request.user, assignment.course.id)
        assignment.browsable = False
        assignment.save()
        eventLogger.info("Hiding assignment [aid: %s]" % str(aid))
        return HttpResponseRedirect(reverse("assignment:list_for_course"))

    @staticmethod
    @login_required
    def delete(request, aid):
        "Delete the assignment"
        # TODO: don't remove, instead just hide

        assignment = get_object_or_404(Assignment, id=aid)
        CoursePermissions.require_course_staff(request.user, assignment.course.id)
        eventLogger.info("Deleting assignment [aid: %s]" % str(aid))
        # course = Assignment._default_manager.get(id=aid).course
        assignment.delete()
        return HttpResponseRedirect(reverse("assignment:list_for_course"))

    @staticmethod
    @login_required
    @chosen_course_required
    def batch_submit(request, aid):
        """
        Batch Submit for the assignment: uploads multiple submission for the assignment
        * Can only be performed by the instructor
        """
        assignment = get_object_or_404(Assignment, id=aid)
        CoursePermissions.require_instructor(request.user, assignment.course.id)
        debugLogger.info(
            'Batch upload for assignment "%s" (%s - course_id: %s) by % s (%s)'
            % (
                str(aid),
                assignment.name,
                assignment.course.id,
                request.user.username,
                str(request.user.id),
            )
        )

        render_dict = dict()
        render_dict["assignment"] = assignment

        render_dict["submissions"] = assignment.assignmentsubmission_set.all()

        render_dict["form"] = form = BatchSubmitForm(
            request.POST or None, request.FILES or None, assignment=assignment
        )

        if request.method == "POST":
            if form.is_valid():
                try:
                    sub = form.save()
                except IntegrityError as e:
                    return JsonResponse(
                        {
                            "is_valid": False,
                            "errors": [
                                'Could not save file "%s", the submission most likely exists already'
                                % form.get_filename()
                            ],
                        }
                    )
                except Exception as e:
                    debugLogger.warn("Error encountered during file upload: " + str(e))
                    return JsonResponse(
                        {
                            "is_valid": False,
                            "errors": [
                                'Encountered unexpected error "%s"' % str(e.args)
                            ],
                        }
                    )
                return JsonResponse(
                    {
                        "is_valid": True,
                        "username": sub.author.user.username,
                        "sid": sub.id,
                        "url": reverse(
                            "assignment:submission_view", kwargs={"sid": sub.id}
                        ),
                    }
                )
            else:
                return JsonResponse(
                    {
                        "is_valid": False,
                        "errors": [e for es in form.errors.values() for e in es],
                    }
                )

        return render(request, "batch-submit.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def submission_list(request, aid):
        "List all submissions for an assignment"

        assignment = get_object_or_404(Assignment, id=aid)
        CoursePermissions.require_course_staff(request.user, assignment.course.id)
        render_dict = dict()
        render_dict["assignment"] = assignment
        return render(request, "submission-list-for-assignment.html", render_dict)

    @staticmethod
    def submission_creation_helper(request, assignment, cm, enforce_deadline=True):
        """
        Handles creating a submission
        This method is used for submitting assignments as well as
        creating calibration assignments (refer to `peer_calibration/views.py`)

        ** NOT A VIEW MEHOD **

        :returns tuple of Form and AssignmentSubmission
        :param request: `HttpRequest`
        :param assignment: `AssignmentSubmission`
        :param cm: `CourseMember` that is creating the submission
        """
        scform = SubmissionComponentForm(
            request.POST.copy() or None,
            request.FILES or None,
            assignment=assignment,
            author=cm,
            enforce_deadline=enforce_deadline,
        )

        for key in scform.data:
            if "rq_text_" in key:
                scform.data[key] = scform.data[key].replace("\r", "")

        if scform.is_valid():
            submission = scform.save()
            return (submission, scform)

        return (None, scform)

    @staticmethod
    def submission_edit_helper(request, submission, cm, enforce_deadline=True):
        """
        Handles editing a submission
        This method is used for submitting assignments as well as
        editing calibration assignments (refer to `peer_calibration/views.py`).

        ** NOT A VIEW MEHOD **

        :returns tuple of Form and AssignmentSubmission
        """
        scform = SubmissionComponentForm(
            request.POST.copy() or None,
            request.FILES or None,
            instance=submission,
            assignment=submission.assignment,
            author=cm,
            enforce_deadline=enforce_deadline,
        )

        for key in scform.data:
            if "rq_text_" in key:
                scform.data[key] = scform.data[key].replace("\r", "")

        if scform.is_valid():
            submission = scform.save()

            submission.attempts += 1
            submission.save()

            return submission, scform

        return None, scform

    @staticmethod
    @login_required
    @chosen_course_required
    def submission_create(request, aid):
        "Create a submission"

        debugLogger.info(
            "Submission create for %s from %s (%s) with course_id %s [%s, %s, %s]"
            % (
                str(aid),
                request.user.username,
                str(request.user.id),
                str(request.session.get("course_id", "")),
                str(request.GET),
                str(request.POST),
                str(request.FILES),
            )
        )

        assignment = get_object_or_404(Assignment, pk=aid)
        if assignment.browsable is False:
            messages.warning(request, "This assignment has not been made Visible")
            return HttpResponseRedirect(reverse("assignment:list_for_course"))

        CoursePermissions.require_course_member(request.user, assignment.course.id)

        cm = CourseBase.get_course_member(request.user, assignment.course.id)

        if not cm.qualified and assignment.qualification_grade is None:
            messages.warning(
                request,
                "You are not yet qualified. You need to complete the quiz to get qualified.",
            )
            return HttpResponseRedirect(reverse("assignment:list_for_course"))

        submission, scform = AssignmentViews.submission_creation_helper(
            request, assignment, cm
        )
        if submission is not None:
            AssignmentViews.post_submission_save(submission, cm, request)
            AssignmentViews.display_form_warnings(request, scform)
            return HttpResponseRedirect(reverse("assignment:list_for_course"))

        render_dict = dict()
        render_dict["assignment"] = assignment
        render_dict["subform"] = scform
        render_dict["is_create"] = True
        return render(request, "submission-create.html", render_dict)

    # TODO: change it to a post-hook later
    @staticmethod
    def post_submission_save(submission, cm, request):
        if submission.assignment.qualification_grade is not None:
            submission.populate_grade()
            submission.save()
            grade = submission.final_grade
            if (
                not cm.qualified
                and grade is not None
                and grade >= submission.assignment.qualification_grade
            ):
                cm.qualified = True
                cm.save()
                messages.success(
                    request,
                    "Congratulations, you have been qualified to solve the essay assignment.",
                )

    @staticmethod
    @login_required
    @chosen_course_required
    def submission_edit(request, sid):
        "Edit a submission"

        debugLogger.info(
            "Submission edit for %s from %s (%s) with course_id %s [%s, %s, %s]"
            % (
                str(sid),
                request.user.username,
                str(request.user.id),
                str(request.session.get("course_id", "")),
                str(request.GET),
                str(request.POST),
                str(request.FILES),
            )
        )

        submission = get_object_or_404(AssignmentSubmission, pk=sid)

        if submission.author.user != request.user:
            messages.warning(request, "You are not the author of this submission.")
            return HttpResponseRedirect(reverse("assignment:list_for_course"))
        # TODO: check if browsable is set to false
        # TODO: only show if not past deadline

        if submission.author.active == False:
            return HttpResponseForbidden(
                "This account has been deactivated, please contact course staff"
            )

        if submission.assignment.max_attempts is not None:
            if submission.attempts >= submission.assignment.max_attempts:
                messages.warning(
                    request,
                    "Maximum number of attempts for this quiz reached. Please contact a TA or the course instructor to edit this submission.",
                )
                return HttpResponseRedirect(reverse("assignment:list_for_course"))

        if submission.assignment.assignment_type == 'quiz':
            time_diff = timezone.now() - submission.time_last_modified
            if time_diff.total_seconds() < float(1800):
                messages.warning(
                    request,
                    "You must wait 30 minutes before trying again.",
                )
                return HttpResponseRedirect(reverse("assignment:list_for_course"))

 
        cm = CourseBase.get_course_member(request.user, submission.assignment.course.id)

        if not cm.qualified and submission.assignment.qualification_grade is None:
            messages.warning(
                request,
                "You are not yet qualified. You need to complete the quiz or contact the course staff to get qualified.",
            )
            return HttpResponseRedirect(reverse("assignment:list_for_course"))

        ret_sub, scform = AssignmentViews.submission_edit_helper(
            request, submission, cm
        )
        if ret_sub is not None:
            AssignmentViews.post_submission_save(submission, cm, request)
            AssignmentViews.display_form_warnings(request, scform)
            return HttpResponseRedirect(reverse("assignment:list_for_course"))

        render_dict = dict()
        render_dict["assignment"] = submission.assignment
        render_dict["subform"] = scform
        render_dict["is_create"] = False
        return render(request, "submission-create.html", render_dict)

    @staticmethod
    def display_form_warnings(request, form):
        if form.warns:
            for warn in form.warns:
                messages.warning(request, warn)

    @staticmethod
    @login_required
    @chosen_course_required
    def submission_view(request, sid):
        "View a submission"

        submission = get_object_or_404(AssignmentSubmission, pk=sid)

        render_dict = dict()
        render_dict["is_author"] = request.user == submission.author.user

        cm = CourseBase.get_course_member(
            request.user, submission.assignment.course.id
        )

        is_staff = CourseBase.is_cm_staff(cm, request.user)

        is_grader= False
        reviews = ReviewAssignment._default_manager.filter(submission=submission)

        for review in reviews:
            if request.user == review.grader.user and review.grader.role == 'student':
                is_grader= True

        render_dict["is_grader"] = is_grader
        render_dict["show_reviews"] = is_staff or (request.user == submission.author.user) or (is_grader and submission.calibration_id==0 and submission.ta_deadline_passed())
        
        if is_staff:
            render_dict["show_grade"] = True
        elif render_dict["is_author"] or (is_grader and submission.calibration_id==0) :
            render_dict["show_grade"] = (
                submission.assignment.assignment_type == QUIZ_ASGN
            #    or submission.student_deadline_passed()
                or submission.ta_deadline_passed()
                # or (cm.is_independent and submission.student_deadline_passed())
                # or ReviewAssignment._default_manager.filter(
                #     submission=submission, grader__role='ta', submitted=True
                # ).exists()
            )
        elif not submission.reviewassignment_set.filter(
                grader__user=request.user
            ).exists():
                raise PermissionDenied(
                    "You are not allowed to view this submission"
                )

        # TODO: check permissions: either author, TA/instructor, or assigned maybe?
        # TODO: (not sure about review assigned)
        # if submission.author.id != request.user.id:
        #   check if TA/instructor
        #     if not CourseMember._default_manager.filter(course=assignment.course, user=request.user).exists():
        #         messages.error(request, 'You are not the author of this submission.')
        #         return HttpResponseRedirect(reverse('assignment:list_for_course'))

        if AssignmentWithReviews._default_manager.filter(
            pk=submission.assignment.id
        ).exists():
            
            users_review = submission.reviewassignment_set.filter(
                grader__user=request.user
            ).first()
            render_dict["users_review_of_sub"] = users_review
            render_dict["can_request_review"] = is_staff and (users_review is None)

        render_dict["sub"] = submission
        return render(request, "submission-view-page.html", render_dict)

    @staticmethod
    @login_required
    def submission_delete(request, sid):
        "Delete a submission"
        # TA cannot delete a submission
        submission = get_object_or_404(AssignmentSubmission, pk=sid)
        eventLogger.warning(
            "Deleting submission (%s) of assignment `%s` [aid: %s] for user %s (%s) by user %s (%s)"
            % (
                str(sid),
                submission.assignment.name,
                str(submission.assignment.id),
                submission.author.user.username,
                str(submission.author.user.id),
                request.user.username,
                str(request.user.id),
            )
        )

        if request.method == "POST":
            try:
                cid = AssignmentBase.delete_submission(request.user, sid)
            except Exception as e:
                messages.error(request, str(e))
        return HttpResponseRedirect(reverse("assignment:list_for_course"))

    # TODO: checkout and do any modifications necessary for questsions (free-form)
    # TODO: maybe comment this part for now
    @staticmethod
    @login_required
    def question_create(request):
        "Create an assignment question"

        # TODO: permissions??
        # TODO: we can't do it like this anymore, right?
        # CoursePermissions.require_course_staff(request.user, course.id)

        MCItemInlineFormSet = inlineformset_factory(
            AssignmentQuestion,
            AssignmentQuestionMultipleChoice,
            form=AssignmentQuestionMultipleChoiceForm,
            fields=("choice_text", "marks"),
            extra=1,
        )

        if request.method == "POST":
            questionForm = AssignmentQuestionForm(data=request.POST)
            if questionForm.is_valid():
                questionForm.save()
                question = questionForm.save()

                if question.category == "MULT":

                    formset = MCItemInlineFormSet(request.POST, instance=question)
                    if formset.is_valid():
                        formset.save()
                        return HttpResponseRedirect("/assignment/question/list/")
                    else:
                        messages.error(request, formset.errors)
                elif question.category == "TEXT":
                    return HttpResponseRedirect("/assignment/question/list/")
                elif question.category == "FILE":
                    return HttpResponseRedirect("/assignment/question/list/")

            else:
                messages.error(request, questionForm.errors)

        else:
            questionForm = AssignmentQuestionForm()
            formset = MCItemInlineFormSet()

        render_dict = dict()
        render_dict["form"] = questionForm
        render_dict["mcitem_formset"] = formset

        return render(request, "assignment-question-create.html", render_dict)

    @staticmethod
    @chosen_course_required
    @login_required
    def question_list(request):
        "Show the list of assignment questions for the current course"

        course = get_object_or_404(Course, pk=request.session["course_id"])

        CoursePermissions.require_course_staff(request.user, course.id)

        render_dict = dict()
        render_dict["questions"] = AssignmentQuestion._default_manager.filter(
            assignment__course=course
        )
        return render(request, "assignment-question-list.html", render_dict)

    @staticmethod
    @login_required
    def question_edit(request, qid):
        "Edit an assignment question"

        question = get_object_or_404(AssignmentQuestion, pk=qid)

        CoursePermissions.require_course_staff(
            request.user, question.assignment.course.id
        )

        items = question.assignmentquestionmultiplechoice_set.all()
        MCItemInlineFormSet = inlineformset_factory(
            AssignmentQuestion,
            AssignmentQuestionMultipleChoice,
            form=AssignmentQuestionMultipleChoiceForm,
            fields=("choice_text", "marks"),
            extra=0,
        )

        questionForm = AssignmentQuestionForm(instance=question)
        formset = MCItemInlineFormSet(instance=question)

        render_dict = dict()
        render_dict["question"] = question
        render_dict["form"] = questionForm
        render_dict["mcitem_formset"] = formset

        if request.method == "POST":

            questionForm = AssignmentQuestionForm(data=request.POST)
            if questionForm.is_valid():
                question = questionForm.save(commit=False)
                question.id = qid
                question.save()

                if question.category == "MULT":

                    # Save the choices
                    formset = MCItemInlineFormSet(data=request.POST, instance=question)
                    if formset.is_valid():
                        formset.save()
                        return HttpResponseRedirect("/assignment/question/list/")

                elif question.category == "TEXT":

                    # Delete all choices associated with this question if any.
                    choices = question.assignmentquestionmultiplechoice_set.all()
                    choices.delete()

                    return HttpResponseRedirect("/assignment/question/list/")

                elif question.category == "FILE":

                    # Delete all choices associated with this question if any.
                    choices = question.assignmentquestionmultiplechoice_set.all()
                    choices.delete()

                    return HttpResponseRedirect("/assignment/question/list/")

            else:
                messages.error(request, questionForm.errors)
                return render(request, "assignment-question-edit.html", render_dict)

        return render(request, "assignment-question-edit.html", render_dict)

    @staticmethod
    @login_required
    def list(request):
        "Display all the assignments in all enrolled courses"

        courses = CourseBase.get_courses(request.user)
        if request.user.is_superuser:
            courses = Course._default_manager.all()

        info = dict()
        from peer_course.views import CourseBase

        # Python has itertools and we probably want to refactor this later
        for course in courses:

            is_student = CourseBase.is_student(request.user, course.id)
            is_ta = CourseBase.is_ta(request.user, course.id)
            is_instructor = CourseBase.is_instructor(request.user, course.id)

            assignments = AssignmentBase.get_visible_assignments(
                course, request.user, is_student
            )

            info[course.id] = {
                "course": course,
                "is_student": is_student,
                "is_ta": is_ta,
                "is_instructor": is_instructor,
                "assignments": assignments,
            }

        render_dict = dict()
        render_dict["info"] = info
        return render(request, "assignment-list-all.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def late_unit_override(request, sid):
        """
            In some situations, the instructor is able
            to override the number of late units used
            for a specific submission.

            Note: the number of late units used can only be decreased.
        """

        submission = get_object_or_404(AssignmentSubmission, pk=sid)
        new_value = request.POST.get("late_units_used", 0)

        redirect_address = reverse("assignment:submission_view", kwargs={"sid": sid})
        try:
            new_value = int(new_value)
        except ValueError:
            messages.warning(request, "Wrong value format specified for late units.")
            return HttpResponseRedirect(redirect_address)

        if new_value >= submission.late_units_used:
            messages.warning(request, "Cannot increase the value of used late units.")
        else:
            old_value = submission.late_units_used
            submission.late_units_used = new_value
            submission.save()
            eventLogger.warning(
                (
                    "Value of late units used for submission %s"
                    + " of user %s (%s) changed from %d to %d by %s (%s)"
                )
                % (
                    str(sid),
                    submission.author.user.username,
                    str(submission.author.user.id),
                    old_value,
                    new_value,
                    request.user.username,
                    str(request.user.id),
                )
            )
            messages.info(
                request, "Successfully modified the value of the late units used."
            )
        return HttpResponseRedirect(redirect_address)
