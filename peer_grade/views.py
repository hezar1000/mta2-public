import csv
import logging

from django.shortcuts import get_object_or_404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render as djangoRender
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError

from itertools import chain
import json

from peer_home.wrappers import render
from peer_assignment.models import SubmissionComponent, AssignmentSubmission
from peer_course.base import *
from peer_course.models import CourseMember
from peer_course.decorators import chosen_course_required
from peer_assignment.base import AssignmentBase
from peer_assignment.models import Assignment
from peer_review.models import ReviewAssignment, ReviewContent
from peer_home.popup_widgets import PopupUtils
from peer_review.base import ReviewBase
from peer_evaluation.models import *
from peer_evaluation.base import EvaluationBase


from .forms import *
from .models import Appeal, InaptReport, GradingItem
from .base import AppealBase, FlagBase, GradeBaseMain
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from .choices import APPEAL_STATUS_CHOICES

# Create your views here.

eventLogger = logging.getLogger("mta.events")


class AppealViews:
    @staticmethod
    @login_required
    @chosen_course_required
    def create(request, sid):
        "Create an appeal"
        render_dict = dict()
        submission = AssignmentBase.get_submission(sid)

        if submission is None:
            messages.error(request, "This submission does not exist.")
            return HttpResponseRedirect(reverse("home:home"))

        if submission.author.user != request.user:
            messages.error(request, "You are not the author of this submission.")
            return HttpResponseRedirect(reverse("home:home"))

        render_dict["submission"] = submission

        # student should be able to create at most one appeal per assignment
        if AppealBase.has_duplicate(submission):
            messages.error(request, "You have already submitted an appeal.")
            apid = AppealBase.find(submission).id
            return HttpResponseRedirect(
                reverse("grade:appeal_view", kwargs={"apid": apid})
            )

        if request.method == "POST":
            instructor= CourseMember._default_manager.filter(course=submission.assignment.course, role='instructor').order_by("id")
            appeal = Appeal(
#                assignee=AppealBase.assign(submission),
                assignee = instructor[0],
                status=0,
                request=request.POST.get("request"),
                submission=submission,
            )
            submission.spotchecking_priority = 1
            submission.save()
            try:
                appeal.full_clean()
            except ValidationError as e:
                # Send the error contained in e.message_dict.
                for err in e.message_dict["request"]:
                    messages.error(request, err)
                return render(request, "appeal-create.html", render_dict)

            appeal.save()
            messages.info(request, "You have successfully submitted an appeal.")
            return HttpResponseRedirect(
                reverse("grade:appeal_view", kwargs={"apid": appeal.id})
            )
        else:
            return render(request, "appeal-create.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def list(request, cid):
        "List all the appeals for the given user"
        # Assigned TA should be able to see this appeal in his/her todo list
        render_dict = dict()
        if CourseBase.is_student(request.user, cid):
            render_dict["is_student"] = True
            appeals = AppealBase.find_by_author(request.user, cid)
            reports = FlagBase.find_by_author(request.user, cid)
        elif CourseBase.is_ta(request.user, cid):
            render_dict["is_student"] = False
            appeals = AppealBase.find_by_assignee(request.user, cid)
            reports = FlagBase.find_by_assignee(request.user, cid)
        elif CourseBase.is_instructor(request.user, cid):
            render_dict["is_student"] = False
            render_dict["is_instructor"] = True
            appeals = AppealBase.find_by_course(cid)
            reports = FlagBase.find_by_course(cid)
        else:
            # render_dict['is_student'] = False
            # render_dict['appeals'] = AppealBase.find_by_assignee(request.user)
            # messages.info(request, 'You are not a TA. Will redirect you to the course page.')
            # return render(request, 'appeal-list.html', render_dict)
            # so students can submit appeals and only TAs can view them
            # instructors and other strangers should be redirect away
            messages.info(
                request, "You are not a course member. Will redirect you to home page."
            )
            return HttpResponseRedirect(reverse("home:home"))
        
        render_dict['items'] = sorted(chain(appeals, reports), key=lambda x: x.order_key())
        return render(request, "appeal-list.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def view(request, apid):
        appeal = AppealBase.get(apid)
        if appeal is None:
            messages.error(request, "Sorry we cannot find that appeal.")
            return HttpResponseRedirect(reverse("home:home"))
        cid = appeal.submission.assignment.course.id
        render_dict = dict()
        render_dict["appeal"] = appeal
        render_dict["appeal_data"] = [("Request", appeal.request or "[empty]")]
        # who can view an appeal? only the students themselves?
        extra_data = [
            ("Status", appeal.get_status_display()),
            ("Response", appeal.response or "[Not available]"),
        ]
        if (
            CourseBase.is_student(request.user, cid)
            and appeal.submission.author.user == request.user
        ):
            render_dict["is_student"] = True
            render_dict["appeal_data"] += extra_data
            return render(request, "appeal-view.html", render_dict)
        elif CourseBase.is_course_staff(request.user, cid):
            if appeal.can_be_modified():
                render_dict["appeal_form"] = AppealForm(instance=appeal)
            else:
                render_dict["appeal_data"] += extra_data
            render_dict["submission"] = appeal.submission
            render_dict["reviews"] = appeal.submission.reviewassignment_set.all()
            render_dict["is_assignee"] = appeal.assignee.user == request.user
            if CourseBase.is_instructor(request.user, cid):
                render_dict["is_instructor"] = True

            return render(request, "appeal-view.html", render_dict)
            # TODO: (or better yet all the reviews) for regrading
            # pass
        else:
            return HttpResponseForbidden()

    @staticmethod
    @csrf_exempt
    def appeal_timer(request):
        if request.method == "POST":
            print ('I am here appeal')
            timespentonpage = request.body
            result = timespentonpage.decode('utf-8')
            user = request.user
            course_member = CourseMember.objects.get(user=user)
            if (course_member.role =='ta'):
                tmp = str(result)
                tmp = tmp.split(" ")
                time, link = tmp[0], tmp[-1]
                text = str(link)
                text_split = text.split(" ")
                appeal_id = text_split[-1].split("/")[-3]
                appeal = Appeal._default_manager.get(id=appeal_id)
                appeal.timer += float(time)
                appeal.save()
                print("Appeal timer now: " + str(appeal.timer), "Time: " + str(time))
                return HttpResponse("success")


    @staticmethod
    @csrf_exempt
    def report_timer(request):
        if request.method == "POST":
            timespentonpage = request.body
            result = timespentonpage.decode('utf-8')
            user = request.user
            course_member = CourseMember.objects.get(user=user)
            if (course_member.role =='ta'):
                tmp = str(result)
                tmp = tmp.split(" ")
                time, link = tmp[0], tmp[-1]
                text = str(link)
                text_split = text.split(" ")
                report_id = text_split[-1].split("/")[-3]
                report = InaptReport._default_manager.get(id=report_id)
                report.timer += float(time)
                report.save()
                print ("Report timer now: " + str(report.timer), "Time: " + str(time))
                return HttpResponse("success")


    @staticmethod
    @login_required
    @chosen_course_required
    def reopen(request, apid):
        "Reopen an appeal so the response/status/assignee can be modified"
        appeal = AppealBase.get(apid)
        CoursePermissions.require_course_staff(
            request.user, appeal.submission.assignment.course.id
        )
        if appeal.can_be_modified():
            messages.warning(request, "Appeal is not closed.")
        else:
            appeal.reopen()
            eventLogger.info(
                "Reopening appeal [apid: %s] of submission [sid: %s] for user %s (%s) by user %s (%s)"
                % (
                    str(apid),
                    appeal.submission.id,
                    appeal.submission.author.user.username,
                    str(appeal.submission.author.user.id),
                    request.user.username,
                    str(request.user.id),
                )
            )
        return HttpResponseRedirect(reverse("grade:appeal_view", kwargs={"apid": apid}))

    @staticmethod
    @login_required
    @chosen_course_required
    def respond(request, apid):
        "(POST) TAs or instructors can respond to the appeal/reassign this to another TA"
        # TODO: change status based on type of change? two buttons?

        # TODO: merge this and appeal_view together

        appeal = AppealBase.get(apid)
        old_assignee = appeal.assignee
        CoursePermissions.require_course_staff(
            request.user, appeal.submission.assignment.course.id
        )
        if not appeal.can_be_modified():
            messages.warning(
                request, "Please reopen the appeal before any modification."
            )
            return HttpResponseRedirect(
                reverse("grade:appeal_view", kwargs={"apid": apid})
            )
        if request.method == "POST":
            form = AppealForm(request.POST, instance=appeal)
            if form.is_valid():
                saved_instance = form.save()
                if old_assignee.user != saved_instance.assignee.user:
                    eventLogger.warning(
                        "Reassigned appeal [apid: %s] from %s (%d) to %s (%d) by %s (%d)"
                        % (
                            str(apid),
                            old_assignee.user.username,
                            old_assignee.user.id,
                            saved_instance.assignee.user.username,
                            saved_instance.assignee.user.id,
                            request.user.username,
                            request.user.id,
                        )
                    )
                if old_assignee.user != request.user:
                    eventLogger.warning(
                        (
                            "Appeal [apid: %s] responded to by someone other"
                            + " than the assignee: by %s (%s) instead of %s (%s)"
                        )
                        % (
                            str(apid),
                            request.user.username,
                            str(request.user.id),
                            old_assignee.user.username,
                            str(old_assignee.user.id),
                        )
                    )
                cid = appeal.submission.assignment.course.id
                return HttpResponseRedirect(
                    reverse("grade:appeal_list", kwargs={"cid": cid})
                )
            else:
                for errors in form.errors.values():
                    for err in errors:
                        messages.error(request, err)
                return HttpResponseRedirect(
                    reverse("grade:appeal_view", kwargs={"apid": apid})
                )
        else:
            messages.error(
                request,
                "Only POST requests are supported for responding/reassigning appeals.",
            )
            return HttpResponseRedirect(reverse("home:home"))


class GradeViews:
    @staticmethod
    @login_required
    @chosen_course_required
    def set_manual_component_grade(request, cid):
        sc = get_object_or_404(SubmissionComponent, pk=cid)

        CoursePermissions.require_course_staff(
            request.user, sc.submission.assignment.course.id
        )

        if request.POST and "grade" in request.POST and request.POST["grade"] != "":
            sc.manual_grade = request.POST["grade"]
            sc.save()

        return HttpResponseRedirect(
            reverse("assignment:submission_view", kwargs={"sid": sc.submission.id})
        )

    @staticmethod
    @login_required
    @chosen_course_required
    def export_comp_ids(request, aid):
        assignment = get_object_or_404(Assignment, pk=aid)
        course = get_object_or_404(Course, pk=request.session["course_id"])

        CoursePermissions.require_course_staff(request.user, assignment.course.id)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="Assignment-%s component ids (%s).csv"'
            % (assignment.name, timezone.now().strftime("%F-%X"))
        )
        
        subs = AssignmentSubmission.objects.filter(assignment= assignment, calibration_id = 0)
        if subs.exists():
            writer = csv.writer(response)
            headers = ["Submission ID"]
            num_sub_comps = SubmissionComponent.objects.filter(submission = subs[0]).count()
            for i in range(num_sub_comps):
                headers += ['Component '+str(i+1)+' ID']

            writer.writerow(headers)

            for sub in subs:
                sub_comps = SubmissionComponent.objects.filter(submission = sub)
                ids = []
                ids.append(sub.id)
                for comp in sub_comps:
                        ids.append(comp.id)

                writer.writerow(ids)  

        return response 



    @staticmethod
    @login_required
    @chosen_course_required
    def export_assignment_grades(request, aid):

        assignment = get_object_or_404(Assignment, pk=aid)
        course = get_object_or_404(Course, pk=request.session["course_id"])

        if course.can_tas_see_reviews:
            CoursePermissions.require_course_staff(request.user, assignment.course.id)
        else:
            CoursePermissions.require_instructor(request.user, assignment.course.id)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="Assignment-%s grades (%s).csv"'
            % (assignment.name, timezone.now().strftime("%F-%X"))
        )

        questions = assignment.questions.all().order_by("id")
        subs= AssignmentSubmission.objects.filter(assignment__id=aid).order_by("id")
        reviews= ReviewAssignment.objects.filter(submission__assignment__id=aid, submitted= True)
        evaluations = EvaluationAssignment.objects.filter ( review__submission__assignment__id=aid, review__submitted=True)

        # If no reviews for this assignment, make stripped down CSV
        if not reviews.exists(): 
            writer = csv.writer(response)
            headers = ["Student ID", "Submission ID", "Calibration ID"] + [q.title for q in questions]
            if subs[0].assignment.assignment_type == 'quiz':
                headers = headers + ['Grade']
            writer.writerow(headers)
            for s in subs:
                row = [s.author.user.username, s.id , s.calibration_id]
                components = [sc for sc in s.components.all().order_by("question__id")]
                pos = 0
                for q in questions:
                    if pos >= len(components) or components[pos].question.id != q.id:
                        row.append("--")
                    else:
#                        row.append(components[pos].final_grade())
                        row.append("--")
                        pos += 1
                if s.assignment.assignment_type == 'quiz':
                    row.append(s.final_grade)
                writer.writerow(row)
            return response

        # Otherwise, write full CSV
        review= reviews[0]
        cts= ReviewContent.objects.filter(review_assignment=review).order_by("choice__question__title")

        # Set up list of CSV columns
        # FIXME: if student ID field changes
        fieldnames = ["Student ID", "Submission ID", "Calibration ID"] \
            + [q.title for q in questions] \
            + ["Review ID", "Reviewer ID", "Reviewer Role", "Reviewer Grade", "Reviewer Weight"] \
            + [rv_cnt.choice.question.title for rv_cnt in cts] \
            + ["Submission Appealed", "Review Reported", "Review Flagged"] \
            + ["Submission Date", "Deadline"]

        # TODO: filter only essay question in a cleaner way, 
        # or give all columns unique names
        # if evaluations.exists():
        #     eval_contents = EvaluationContent.objects.filter(
        #         evaluation=evaluations[0], 
        #         submission_component__question__title='Q1',
        #     ).order_by("choice__question__title")
        #     fieldnames += [eval_cnt.choice.question.title for eval_cnt in eval_contents]
        # For now, just get the name of one...
        eval_content = EvaluationContent.objects.filter(evaluation__review__submission__assignment__id=aid, submission_component__question__title='Q1')
        if eval_content.exists():
            ec = eval_content[0]
            fieldnames += [ec.choice.question.title]

        writer = csv.DictWriter(response, fieldnames)
        writer.writeheader()

        for s in subs:
            # Get reviews from students in course and instructors separately
            # Works around a bug where some historical instructor grades were uploaded by a member of a different course
            rvs_in_course = s.reviewassignment_set.filter(grader__course_id=s.assignment.course_id)
            rvs_instructor = s.reviewassignment_set.filter(grader__role='instructor')
            rvs = rvs_in_course.union(rvs_instructor).all()
            if rvs.exists():
                for r in rvs:
                    # Student/assignment/reviewer info
                    sub_date_format = '%Y-%m-%d %H:%M:%S'
                    row = {
                        'Student ID': s.author.user.username,
                        'Submission ID': s.id,
                        'Calibration ID': s.calibration_id,
                        # Exclude median grade for each question...
                        'Review ID': r.id,
                        'Reviewer ID': r.grader.user.username,
                        'Reviewer Role': r.grader.role,
                        'Reviewer Grade': r.assigned_grade,
                        'Reviewer Weight': r.markingload,
                        'Submission Appealed': hasattr(s, 'appeal'),
                        'Review Reported': r.inaptreport_set.count() > 0,
                        'Review Flagged': hasattr(r, 'flag'),
                        'Submission Date': '' if r.submission_date is None else r.submission_date.strftime(sub_date_format),
                        'Deadline': r.deadline().strftime(sub_date_format),
                    }

                    # Component-wise grades
                    contents = ReviewContent.objects.filter(review_assignment=r).order_by("choice__question__title")
                    for rv_cnt in contents:
                        question_title = rv_cnt.choice.question.title
                        grade = rv_cnt.assigned_grade()
                        row[question_title] = grade

                    # TA evaluations
                    eval_contents = EvaluationContent.objects.filter(
                        evaluation__review=r, 
                        submission_component__question__title='Q1',
                        evaluation__review__submitted=True
                    )
                    if eval_contents.exists():
                        eval_contents = eval_contents.order_by("choice__question__title")
                        for eval_cnt in eval_contents:
                            eval_question = eval_cnt.choice.question.title
                            eval_grade = eval_cnt.choice.marks
                            row[eval_question] = eval_grade

                    writer.writerow(row)

                    # For posterity: old code for median question grades
                    # components = [sc for sc in s.components.all().order_by("question__id")]
                    # pos = 0
                    # for q in questions:
                    #     if pos >= len(components) or components[pos].question.id != q.id:
                    #         row.append("--")
                    #     else:
                    #         row.append(components[pos].final_grade())
                    #         pos += 1

            else:
                row = {
                    'Student ID': s.author.user.username,
                    'Submission ID': s.id,
                    'Calibration ID': s.calibration_id
                }
                writer.writerow(row)

        return response

    @staticmethod
    @login_required
    @chosen_course_required
    def import_assignment_grades(request, aid):

        assignment = get_object_or_404(Assignment, pk=aid)
        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict = dict()

        render_dict["assignment"] = assignment
        render_dict["cid"] = assignment.course.id
        render_dict["model_name"] = "review"

        if course.can_tas_see_reviews:
            CoursePermissions.require_course_staff(request.user, assignment.course.id)
        else:
            CoursePermissions.require_instructor(request.user, assignment.course.id)


        if request.method == 'POST':
            form = ImportStudentGrades(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['file']
                # let's check if it is a csv file
                if not csv_file.name.endswith('.csv'):
                    messages.error(request, 'This is not a CSV file.')
                else:
                    count= GradeBaseMain.import_student_grades(csv_file)
                    messages.success(request, "Successfully assigned %d grades to students." % count)
                    return HttpResponseRedirect(reverse("review:assignment_review_list", kwargs={"aid": aid}))

        
        form = ImportStudentGrades()

        render_dict["form"] = form
        return render(request, "review-upload-student-grades.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def upload_component_grades(request, aid):

        assignment = get_object_or_404(Assignment, pk=aid)
        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict = dict()

        render_dict["assignment"] = assignment
        render_dict["cid"] = assignment.course.id
        render_dict["model_name"] = "review"

        if course.can_tas_see_reviews:
            CoursePermissions.require_course_staff(request.user, assignment.course.id)
        else:
            CoursePermissions.require_instructor(request.user, assignment.course.id)


        if request.method == 'POST':
            form = UploadComponentGrades(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['file']
                # let's check if it is a csv file
                if not csv_file.name.endswith('.csv'):
                    messages.error(request, 'This is not a CSV file.')
                else:
                    count= GradeBaseMain.upload_component_grades(csv_file)
                    messages.success(request, "Successfully uploaded %d grades for students." % count)
                    return HttpResponseRedirect(reverse("review:assignment_review_list", kwargs={"aid": aid}))

        
        form = UploadComponentGrades()

        render_dict["form"] = form
        return render(request, "review-upload-component-grades.html", render_dict)


    @staticmethod
    @login_required
    @chosen_course_required
    def upload_grading_items(request):

        course = get_object_or_404(Course, pk=request.session["course_id"])
        render_dict = dict()


        CoursePermissions.require_course_staff(request.user, course.id)

        if request.method == 'POST':
            form = UploadGradingItems(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['file']
                # let's check if it is a csv file
                if not csv_file.name.endswith('.csv'):
                    messages.error(request, 'This is not a CSV file.')
                else:
                    count= GradeBaseMain.upload_grading_items(csv_file, course.id)
                    messages.success(request, "Successfully uploaded %d grades for students." % count)
                    # return HttpResponseRedirect("gradebook.html")

        
        form = UploadGradingItems()

        render_dict["form"] = form
        return render(request, "upload_grade_items.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def show_grade_book(request):
        cid = request.session["course_id"]
        course = Course._default_manager.get(id=cid)
        request.session["course_id"] = course.id
        coursemember = CourseBase.get_course_member(request.user, course.id)
        render_dict=dict()
        if coursemember.role == 'student':
            render_dict["grade_items"] = EvaluationBase.get_my_grades(request.user, course)
            # with open('./vzF3THBgrUoGkqhA.json', 'r') as fp:
            #     data = json.load(fp)
            # render_dict["review_grades"] = data[coursemember.user.username]
            participation_grades = GradingItem.objects.filter(gradee = coursemember, grade_type = 'Participation').order_by('-grading_period')
            review_grades  = GradingItem.objects.filter(gradee = coursemember, grade_type = 'Peer review').order_by('-grading_period')
            render_dict['participation_grades'] = participation_grades
            render_dict['review_grades'] = review_grades
            return render(request, "gradebook.html", render_dict) 
        if coursemember.role == 'instructor':
            render_dict['is_instructor'] = True
            students = CourseMember.objects.filter(course_id = cid, role = 'student', active = True)
            assignments = Assignment.objects.filter(course= course).exclude(assignment_type= 'quiz').exclude(submission_required= False)
            quizes = Assignment.objects.filter(course= course, assignment_type= 'quiz')

            # render_dict['students'] = list(students)
            render_dict['assignments'] = list(assignments)
            render_dict['quizes'] = list(quizes)
            grade_dict= dict()
            grade_dist_quiz = dict()
            for student in students:
                grade_dict[student]=[]
                grade_dist_quiz[student]=[]

                for assignment in assignments:
                    subs = AssignmentSubmission.objects.filter(author = student, assignment= assignment)
                    if subs.exists():
                        grade_dict[student].append(subs[0])
                    else:
                        grade_dict[student].append('not submitted')
                for quiz in quizes:
                    subs = AssignmentSubmission.objects.filter(author = student, assignment= quiz)
                    if subs.exists():
                        grade_dist_quiz[student].append(subs[0])
                    else:
                        grade_dist_quiz[student].append('not submitted')

            # print (grade_dict)
            print(students)
            return render(request, "gradebook.html", {'render_dict': render_dict, 'grade_dict': grade_dict, 'grade_dict_quiz': grade_dist_quiz})



    @staticmethod
    @login_required
    @chosen_course_required
    def export_course_grades(request):

        cid = request.session["course_id"]
        course = Course._default_manager.get(id=cid)
      
        CoursePermissions.require_instructor(request.user, course.id)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="Course-%s grades (%s).csv"'
            % (course.displayname, timezone.now().strftime("%F-%X"))
        )

        students = CourseMember.objects.filter(course_id = course.id, role = 'student', active = True)
        assignments = Assignment.objects.filter(course= course).exclude(assignment_type= 'quiz').exclude(submission_required= False)

        writer = csv.writer(response)
        # FIXME: if student ID field changes
        headers = []
        headers += ["Student name", "Student ID"]
        headers += [assignment.name for assignment in assignments]
        writer.writerow(headers)

        # render_dict['students'] = list(students)
        for student in students:
            row=[student.get_user_fullname(), student.get_user_id()]
            for assignment in assignments:
                subs = AssignmentSubmission.objects.filter(author = student, assignment= assignment)
                if subs.exists():
                    if not subs[0].final_grade is None:
                        row.append(round(subs[0].final_grade*100/subs[0].assignment.max_total_grade,2))
                    else:
                        row.append('Not available')
                else:
                    row.append('Not submitted')

            writer.writerow(row)

        return response   

class FlagViews:
    @staticmethod
    @login_required
    @chosen_course_required
    def report_review(request, rid):
        review = get_object_or_404(ReviewAssignment, pk=rid)

        if review.grader.role != "student":
            messages.warning(request, "You can only mark report inappropriate student reviews.")
            return HttpResponseRedirect(reverse("home:home"))

        render_dict = dict()
        render_dict["review"] = review
        render_dict["remove_navbar"] = True

        cm = CourseBase.get_course_member(
            request.user, review.submission.assignment.course.id
        )

        if cm is None:
            messages.warning(request, "You are not enrolled in this course")
            return HttpResponseRedirect(reverse("home:home"))

        prior_report = InaptReport._default_manager.filter(review=review, reporter=cm)

        # TODO: can a review be reported multiple times?

        if prior_report.exists():
            messages.warning(
                request,
                "You have already reported this review for being inappropriate.",
            )
            return HttpResponseRedirect(
                reverse("review:review_view", kwargs={"rid": rid})
            )

        render_dict["form"] = form = InaptReportForm(
            request.POST or None, initial={"reporter": cm, "review": review}
        )
        if form.is_valid():
            form.save()
            return PopupUtils.call_parent_continuation()

        return render(request, "report-create.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def report_view(request, rid):
        report = get_object_or_404(InaptReport, pk=rid)
        review = report.review

        CoursePermissions.require_course_staff(
            request.user, review.submission.assignment.course.id
        )

        render_dict = dict()
        render_dict["report"] = report
        render_dict["model"] = review
        render_dict["components"] = ReviewBase.get_review_components_dict(review)
        # render_dict["time_period"] = AssignmentBase.assign_time_period(
        #     review.submission.assignment.id, review.submission.author.user.id
        # )
        if review.question is not None:
            render_dict["questions"] = [review.question.id]
        else:
            render_dict["questions"] = None

        return render(request, "report-view.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def flag_review(request, rid):

        review = get_object_or_404(ReviewAssignment, pk=rid)

        render_dict = dict()
        render_dict["model"] = review

        CoursePermissions.require_course_staff(
            request.user, review.submission.assignment.course.id
        )

        cm = CourseBase.get_course_member(
            request.user, review.submission.assignment.course.id
        )

        render_dict["form"] = form = InaptFlagForm(
            request.POST or None, initial={"reporter": cm, "review": review}
        )

        if form.is_valid():
            form.save()
            review.inaptreport_set.update(closed=True)
            messages.info(request, "The review has been taken down")
            review.submission.populate_grade()
            review.submission.save()
            review.visible = False
            review.save()
            return HttpResponseRedirect(reverse("review:view", kwargs={"rid": rid}))

        return render(request, "flag-create.html", render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def report_dismiss(request, rid):
        review = get_object_or_404(ReviewAssignment, pk=rid)

        render_dict = dict()
        render_dict["model"] = review

        CoursePermissions.require_course_staff(
            request.user, review.submission.assignment.course.id
        )

        review.inaptreport_set.update(closed=True)
        messages.info(request, "The report has been dismissed")

        return HttpResponseRedirect(reverse("review:view", kwargs={"rid": rid}))
