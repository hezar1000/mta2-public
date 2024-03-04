import csv
import subprocess
from django.shortcuts import get_object_or_404, HttpResponseRedirect, HttpResponse
from django.utils import timezone
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
from .models import Appeal, InaptReport
from .base import AppealBase, FlagBase, GradeBaseMain
from peer_evaluation.models import EvaluationAssignment, EvaluationContent
from walrus import *


def export_to_csv_assignment_grades(aid):
    assignment = get_object_or_404(Assignment, pk=aid)
    course = get_object_or_404(Course, pk=assignment.course.id)
    filename='./for_inference/Assignment-%s-grades.csv' % (assignment.name)
    with open(filename, 'w', newline='') as response:  
        questions = assignment.questions.all().order_by("id")
        subs= AssignmentSubmission.objects.filter(assignment__id=aid).order_by("id")
        reviews= ReviewAssignment.objects.filter(submission__assignment__id=aid, submitted= True)
        evaluations = EvaluationAssignment.objects.filter ( review__submission__assignment__id=aid, review__submitted=True)
        # If no reviews for this assignment, make stripped down CSV
        if not reviews.exists(): 
            writer = csv.writer(response)
            headers = ["Student ID", "Submission ID", "Calibration ID"] + [q.title for q in questions]
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
                writer.writerow(row)
            response.close()
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
        response.close()



def import_ci_from_file(csv_file, supervised_threshold, cid):
    course = Course._default_manager.get(id=cid)
    print(course)
    print(csv_file)
    with open(csv_file, 'r', newline='') as csvfile:
        for row in csv.reader(csvfile, delimiter=',', quotechar='|'):
            stus= CourseMember._default_manager.filter(user__username=row[0], course__id=cid)
            if stus.exists():
                stu=stus[0]
                stu.lower_confidence_bound= float(row[1])
                stu.markingload=  float(row[2])
                stu.upper_confidence_bound= float(row[3])
                if supervised_threshold is not None:                   
                    if stu.lower_confidence_bound < supervised_threshold :
                        stu.is_independent= False
                    else:
                        stu.is_independent= True
                stu.save()


# def export_to_redis_assignment_grades(db,cid):
#     lock = db.lock('inference-lock')
#     lock.acquire()
#     print('export started and lock acquired')
#     row_list = []
#     temp_row_list=[]
#     assignments = Assignment._default_manager.filter(course_id=cid, assignment_type = 'text').order_by("id")
#     for week, assignment in enumerate(assignments):
#         aid= assignment.id
#         course = get_object_or_404(Course, pk=assignment.course.id)
#         questions = assignment.questions.all().order_by("id")
#         subs= AssignmentSubmission.objects.filter(assignment__id=aid).order_by("id")
#         reviews= ReviewAssignment.objects.filter(submission__assignment__id=aid, submitted= True)
#         evaluations = EvaluationAssignment.objects.filter ( review__submission__assignment__id=aid, review__submitted=True)
#         for s in subs:
#             # Get reviews from students in course and instructors separately
#             # Works around a bug where some historical instructor grades were uploaded by a member of a different course
#             rvs_in_course = s.reviewassignment_set.filter(grader__course_id=s.assignment.course_id)
#             rvs_instructor = s.reviewassignment_set.filter(grader__role='instructor')
#             rvs = rvs_in_course.union(rvs_instructor).all()
#             if rvs.exists():
#                 for r in rvs:
#                     row_list.append(s.author.user.username+'_'+str(r.id))
#                     temp_row_list.append(s.author.user.username+'_'+str(r.id))
#                     row_list[-1]= db.Hash(s.author.user.username+'_'+str(r.id))
#                     # Student/assignment/reviewer info
#                     sub_date_format = '%Y-%m-%d %H:%M:%S'
#                     row = {
#                         'Student ID': s.author.user.username,
#                         'Submission ID': s.id,
#                         'Calibration ID': s.calibration_id,
#                         # Exclude median grade for each question...
#                         'Review ID': r.id,
#                         'Reviewer ID': r.grader.user.username,
#                         'Reviewer Role': r.grader.role,
#                         'Reviewer Grade': r.assigned_grade,
#                         'Reviewer Weight': r.markingload,
#                         'Submission Appealed': str(hasattr(s, 'appeal')),
#                         'Review Reported': str(r.inaptreport_set.count() > 0),
#                         'Review Flagged': str(hasattr(r, 'flag')),
#                         'Submission Date': '' if r.submission_date is None else r.submission_date.strftime(sub_date_format),
#                         'Deadline': r.deadline().strftime(sub_date_format),
#                         'Week': week+1
#                     }
#                     # Component-wise grades
#                     contents = ReviewContent.objects.filter(review_assignment=r).order_by("choice__question__title")
#                     for rv_cnt in contents:
#                         question_title = rv_cnt.choice.question.title
#                         grade = rv_cnt.assigned_grade()
#                         row[question_title] = grade
#                     # TA evaluations
#                     eval_contents = EvaluationContent.objects.filter(
#                         evaluation__review=r, 
#                         submission_component__question__title='Q1',
#                         evaluation__review__submitted=True
#                     )
#                     if eval_contents.exists():
#                         eval_contents = eval_contents.order_by("choice__question__title")
#                         for eval_cnt in eval_contents:
#                             eval_question = eval_cnt.choice.question.title
#                             eval_grade = eval_cnt.choice.marks
#                             row[eval_question] = eval_grade
#                     row_list[-1].update(row)
#     list_of_submissions_with_reviews = db.List('list_of_submissions_with_reviews')
#     list_of_submissions_with_reviews.extend(temp_row_list)
#     lock.release()
#     print('export ended and lock released')
