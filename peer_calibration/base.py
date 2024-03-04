import math
import random
import re
from django.utils import timezone
from django.db.models import Q

from tqdm import tqdm

from scipy import stats
import numpy as np
from peer_calibration.inference import run_gibbs
import pickle




from peer_course.models import Course, CourseMember
from peer_course.base import CourseBase
from peer_assignment.models import Assignment, AssignmentSubmission, SubmissionComponent
from peer_review.models import *
from peer_review.base import ReviewBase
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden


class CalibrationBase:


    @staticmethod
    def points(question, choice):
        if question == 1 :
            points_dict = {
                0 : 0,
                1 : 9,
                2 : 6,
                3 : 5,
                4 : 3,
                5 : 4,
            }
            return points_dict.get(choice)
        elif question ==2:
            points_dict = {
                0 : 0,
                1 : 9,
                2 : 6,
                3 : 3,
                4 : 3,
                5 : 7,
            }
            return points_dict.get(choice)     
        elif question ==3:
            points_dict = {
                0 : 0,
                1 : 9,
                2 : 9,
                3 : 5,
                4 : 2,
                5 : 6,
            }
            return points_dict.get(choice)      
        elif question ==4:
            points_dict = {
                0 : 0,
                1 : 0,
                2 : 9,
                3 : 4,
                4 : 2,
                5 : 3,
            }
            return points_dict.get(choice)               
        else: 
            return 0


    @staticmethod
    def weight(question, choice):
        if question == 1 :
            weights_dict = {
                0 : 0,
                1 : 2.9,
                2 : 1.8,
                3 : 1.5,
                4 : 1.0,
                5 : 1.3,
            }
            return weights_dict.get(choice)
        elif question ==2:
            weights_dict = {
                0 : 0,
                1 : 2.9,
                2 : 1.8,
                3 : 1.0,
                4 : 1.0,
                5 : 2.2,
            }
            return weights_dict.get(choice)     
        elif question ==3:
            weights_dict = {
                0 : 0,
                1 : 4.5,
                2 : 4.5,
                3 : 2.4,
                4 : 1,
                5 : 2.8,
            }
            return weights_dict.get(choice)      
        elif question ==4:
            weights_dict = {
                0 : 0,
                1 : 0,
                2 : 3.7,
                3 : 1.8,
                4 : 1.0,
                5 : 1.2,
            }
            return weights_dict.get(choice)               
        else: 
            return 0

    #only for essay 1 calibrations in CPSC430, this function ensures that students don't get calibrations for their own assigned time period       
    @staticmethod
    def filter_calibrations(grader):
        if grader.id % 9 == 1:
            return (7018,7023,7029)
        elif grader.id % 9 == 2:
            return (7019,7021,7028)
        elif grader.id % 9 == 3:
            return (7024)
        elif grader.id % 9 == 4:
            return (7030)
        elif grader.id % 9 == 5:
            return (7020, 7026)
        elif grader.id % 9 == 6:
            return (7027, 7032, 7034, 7035)
        elif grader.id % 9 == 7:
            return (7025, 7031, 7033)
        elif grader.id % 9 == 8:
            return (7022)
        else:
            return None




    @staticmethod
    def get_calibrations(aid, gr):
        subs=AssignmentSubmission._default_manager.filter(assignment__id=aid).exclude(calibration_id=0).exclude(reviewassignment__grader=gr)
        if aid == 63:
            for sub_id in CalibrationBase.filter_calibrations(gr):
                subs= subs.exclude(id=sub_id)

        if subs.exists():
            return subs
        else:
            return -1

    @staticmethod
    def get_all_calibrations(aid, gr):
        # this functions return all of the calibration reviews except those for assignment aid
        if (
            AssignmentSubmission._default_manager.all()
            .exclude(calibration_id=0)
            .exclude(assignment__id=aid)
            .exclude(reviewassignment__grader=gr)
        ).exists():
            # .exclude(late_units_used= gr.user.id).exists(): this line is only for assignment 1.
            return (
                AssignmentSubmission._default_manager.all()
                .exclude(calibration_id=0)
                .exclude(assignment__id=aid)
                # .exclude(late_units_used=gr.user.id) this line is only for assignment 1.
                .exclude(reviewassignment__grader=gr)
            ).order_by("-time_last_modified")
        else:
            return -1

    @staticmethod
    def calculate_calibration_points(calibration):
        cal_dict = dict()
        cal_dict["components"] = {}
        #points = 10
        obtained_points=0
        total_points=0
        negative_points=0
        content_queryset = ReviewContent._default_manager.filter(
            review_assignment=calibration
        ).order_by("choice__question__title")
        groundtruth_review = ReviewAssignment._default_manager.filter(
            submission=calibration.submission, is_groundtruth=True
        ).first()
        if ReviewContent._default_manager.filter(
            review_assignment=groundtruth_review
        ).exists():
            for sc in calibration.submission.components.all():
                # TODO: refactor this part out
                content_queryset = ReviewContent._default_manager.filter(
                    review_assignment=calibration, submission_component=sc
                ).order_by("choice__question__title")
                groundtruth_content_queryset = ReviewContent._default_manager.filter(
                    review_assignment=groundtruth_review, submission_component=sc
                ).order_by("choice__question__title")
                contents = list()

                for i in range(len(content_queryset)):
                    gourndtruth_choice_id = int(
                        groundtruth_content_queryset[i].choice.id
                    )
                    gourndtruth_chosen = RubricQuestionMultipleChoiceItem._default_manager.get(
                        pk=gourndtruth_choice_id
                    )
                    groundtruth_grade = gourndtruth_chosen.marks
            #        total_points += CalibrationBase.points(i,groundtruth_grade)

                for i in range(len(content_queryset)):
                    content_dict = dict()

                    content_dict["question"] = content_queryset[i].choice.question.text
                    content_dict["content_obj"] = content_queryset[i]
                    content_dict["reason"] = content_queryset[i].reason
                    content_dict["groundtruth_reason"] = groundtruth_content_queryset[
                        i
                    ].reason

                    # if content_obj.choice.question.category == MULTIPLECHOICE :
                    choice_id = int(content_queryset[i].choice.id)
                    chosen = RubricQuestionMultipleChoiceItem._default_manager.get(
                        pk=choice_id
                    )
                    content_dict["answer"] = chosen.text
                    grade = chosen.marks
                    content_dict["grade"] = grade
                    content_dict["max_grade"] = chosen.question.max_grade()

                    gourndtruth_choice_id = int(
                        groundtruth_content_queryset[i].choice.id
                    )
                    gourndtruth_chosen = RubricQuestionMultipleChoiceItem._default_manager.get(
                        pk=gourndtruth_choice_id
                    )
                    content_dict["groundtruth_answer"] = gourndtruth_chosen.text
                    groundtruth_grade = gourndtruth_chosen.marks
                    content_dict["groundtruth_grade"] = groundtruth_grade

                    # elif content_obj.choice.question.category == TEXT :
                    #     content_dict['answer'] = content_obj.choice.id

                    # elif content_obj.choice.question.category == FILE :
                    #     pass
                    # content_dict['answer'] = ReviewUtils.get_file_links(
                    #     content_obj.choice.question, review)
        #            negative_points -= CalibrationBase.weight(i,groundtruth_grade) * ((grade - groundtruth_grade) ** 2)
                    contents.append(content_dict)
                cal_dict["components"][sc.id] = contents
        #    obtained_points = max(0,total_points+negative_points)
            return (cal_dict, obtained_points, total_points)
        else:
            return (cal_dict, -1,-1)

    @staticmethod
    def round_up(n, decimals=0):
        multiplier = 10 ** decimals
        return math.ceil(n * multiplier) / multiplier

    @staticmethod
    def calculate_score(student, course):
        #    calibrations = ReviewAssignment._default_manager.filter(
        #        submission__assignment__course=course, grader=student, submitted=True).exclude(
        #            submission__calibration_id=0).order_by(
        #                '-modification_date')

        student_reviews = ReviewAssignment._default_manager.filter(
            submission__assignment__course=course, grader=student, submitted=True
        ).order_by("-modification_date")

        total_points_overfive = 0
        obtained_points_overfive = 0
        evaluation_considered = False
        review_status = False
        num_considered_reviews = 0

        for student_review in student_reviews:
            if num_considered_reviews >= 5:
                break
            if student_review.submission.calibration_id != 0:
                if not student.is_independent or student_review.modification_date < student.time_is_independent_changed:
                    calibration = student_review
                    if ReviewContent._default_manager.filter(
                        review_assignment=calibration
                    ).exists():
                        (_, obtained_points, total_points) = CalibrationBase.calculate_calibration_points(
                            calibration
                        )
                        if obtained_points == -1:
                            return (review_status, -1, False)
                        else:
                            obtained_points_overfive += obtained_points
                            total_points_overfive += total_points
                            num_considered_reviews += 1
            else:
                obtained_points = student_review.evaluation_grade()
                if obtained_points is not None:
                    obtained_points_overfive +=   2 * obtained_points
                    total_points_overfive += 20 
                    num_considered_reviews += 1
                    evaluation_considered = True
        if total_points_overfive ==0:
            return (review_status, 0, evaluation_considered)   
        else:    
            review_status = obtained_points_overfive/total_points_overfive >= 0.75
            percentage= CalibrationBase.round_up((obtained_points_overfive/total_points_overfive) * 100,2)
            return (review_status, percentage, evaluation_considered)

        # for calibration in calibrations[:5]:
        #     if ReviewContent._default_manager.filter(review_assignment=calibration).exists():
        #         points = 10
        #         content_queryset = ReviewContent._default_manager.filter(
        #             review_assignment=calibration,
        #         ).order_by('choice__question__pk')
        #         groundtruth_review = ReviewAssignment._default_manager.filter(
        #             submission=calibration.submission, is_groundtruth=True)
        #         if ReviewContent._default_manager.filter(
        #                 review_assignment=groundtruth_review).exists():
        #             groundtruth_content_queryset = ReviewContent._default_manager.filter(
        #                 review_assignment=groundtruth_review,).order_by('choice__question__pk')
        #             for i in range(len(content_queryset)):
        #                 choice_id = int(content_queryset[i].choice.id)
        #                 chosen = RubricQuestionMultipleChoiceItem._default_manager.get(
        #                     pk=choice_id)
        #                 grade = chosen.marks
        #                 gourndtruth_choice_id = int(
        #                     groundtruth_content_queryset[i].choice.id)
        #                 gourndtruth_chosen = RubricQuestionMultipleChoiceItem._default_manager.get(
        #                     pk=gourndtruth_choice_id)
        #                 groundtruth_grade = gourndtruth_chosen.marks
        #                 points -= (grade - groundtruth_grade)**2
        #             total_points += max(points, 0)
        #             print('total points: %s' % total_points)
        #             review_status = (total_points > 34)
        #         else:
        #             return (review_status,-1)
        # return (review_status, total_points)

    @staticmethod
    def check_if_independent(student, course):
        output = CalibrationBase.calculate_score(student, course)
        return output[0]

    @staticmethod
    def calibration_total_score(student, course):
        gr = CourseBase.get_course_member(student, course.id)
        output = CalibrationBase.calculate_score(gr, course)
        return output[1]

    @staticmethod
    def check_if_evaluation_considered(student, course):
        gr = CourseBase.get_course_member(student, course.id)
        output = CalibrationBase.calculate_score(gr, course)
        return output[2]

    @staticmethod
    def assign_calibration_reviews(aid, num_calibration_reviews):
        # calibration_submissions = AssignmentSubmission._default_manager.filter(
        #     assignment_id=aid).exclude(calibration_id=0).all()
        supervised_students = ReviewBase.get_supervised_students_for_assignment(aid)

        for i in supervised_students:
            calibration_submissions = CalibrationBase.get_all_calibrations(aid, i)
            #    num_already_assgned_cals = ReviewAssignment._default_manager.filter(
            #        submission__id=aid, grader=i).exclude(submission__calibration_id=0).count()
            #    num_cal = num_calibration_reviews - num_already_assgned_cals
            if calibration_submissions == -1:
                return HttpResponseForbidden("Not enough calibration essays")
            else:
                # sampled_calibration = random.sample(list(calibration_submissions), num_calibration_reviews)
                for j in range(num_calibration_reviews):
                    ReviewAssignment._default_manager.create(
                        submission=calibration_submissions[j], grader=i
                    )

    @staticmethod
    def convertGradeScale(grades):
        for (old_grade, new_grade) in [(25, 5), (20, 4), (16.25, 3), (12.5, 2), (6.25, 1)]:
            grades[np.where(grades == old_grade)] = new_grade
        return grades
    
    @staticmethod
    def calculate_score_gibbs(student, course, number_to_include):
        student_reviews = ReviewAssignment._default_manager.filter(
            submission__assignment__course=course, grader=student, submitted=True
        ).order_by("-submission_date")
        # TODO: look for good question title instead? "starts with essay"?
        bad_essay_question_titles = ['Outline', 'References']
        rubric_question_titles = ['1. Argument structure', '4. English', '2. Evidence', '3. Subject matter']
        observed_grades=[]
        true_grades=[]
        with open('./all_grades.pkl','rb') as f:
            all_grades = pickle.load(f)
        clamped_true_grades = []
        if len(student_reviews) >= number_to_include:
            if number_to_include == 16:
                for student_review in student_reviews[:number_to_include]:
                    if student_review.submission.id in all_grades.keys():
                    #find true_grades:
                    # clamped_true_grades = []
                        observed_component_grades = []
                        clamped_true_grades.append(all_grades[student_review.submission.id])
                        sub_components = SubmissionComponent._default_manager \
                            .filter(submission= student_review.submission) \
                            .exclude(question__title__in=bad_essay_question_titles)
                        observed_contents= ReviewContent._default_manager.filter(review_assignment=student_review, submission_component= sub_components[0]).order_by("choice__question__title")
                        for question in rubric_question_titles:
                            for obs_cnt in observed_contents:
                                if question == obs_cnt.choice.question.title:
                                    observed_component_grades.append(obs_cnt.assigned_grade())
                        observed_grades.append(observed_component_grades)
                # observed_grades = 20 * np.ones((15,4))
                # clamped_true_grades = 20 * np.ones((15,4))
                graph = np.ones(len(observed_grades))
            else: 
                for student_review in student_reviews[1:number_to_include+1]:
                    if student_review.submission.id in all_grades.keys():
                    #find true_grades:
                    # clamped_true_grades = []
                        observed_component_grades = []
                        clamped_true_grades.append(all_grades[student_review.submission.id])
                        sub_components = SubmissionComponent._default_manager \
                            .filter(submission= student_review.submission) \
                            .exclude(question__title__in=bad_essay_question_titles)
                        observed_contents= ReviewContent._default_manager.filter(review_assignment=student_review, submission_component= sub_components[0]).order_by("choice__question__title")
                        for question in rubric_question_titles:
                            for obs_cnt in observed_contents:
                                if question == obs_cnt.choice.question.title:
                                    observed_component_grades.append(obs_cnt.assigned_grade())
                        observed_grades.append(observed_component_grades)
                # observed_grades = 20 * np.ones((15,4))
                # clamped_true_grades = 20 * np.ones((15,4))
                graph = np.ones(len(observed_grades))

        else:
            for student_review in student_reviews:
                if student_review.submission.id in all_grades.keys():
                #find true_grades:
                # clamped_true_grades = []
                    clamped_true_grades.append(all_grades[student_review.submission.id])
                    observed_component_grades = []
                    sub_components = SubmissionComponent._default_manager \
                        .filter(submission= student_review.submission) \
                        .exclude(question__title__in=bad_essay_question_titles)
                    observed_contents= ReviewContent._default_manager.filter(review_assignment=student_review, submission_component= sub_components[0]).order_by("choice__question__title")
                    for question in rubric_question_titles:
                        for obs_cnt in observed_contents:
                            if question == obs_cnt.choice.question.title: 
                                observed_component_grades.append(obs_cnt.assigned_grade())
                    observed_grades.append(observed_component_grades)
            # observed_grades = 20 * np.ones((len(student_reviews),4))
            # clamped_true_grades = 20 * np.ones((len(student_reviews),4))
            graph = np.ones(len(observed_grades))
        observed_grades = np.array(observed_grades)
        clamped_true_grades = np.array(clamped_true_grades)
        mu_s= 4
        sigma_s= 1.5
        alpha_effort= 6
        beta_effort= 2
        alpha_rel = student.lower_confidence_bound * student.lower_confidence_bound
        beta_rel= student.lower_confidence_bound
        tau_l= 4
        hyperparams= (float(mu_s),float(sigma_s), float(alpha_effort), float(beta_effort), float(alpha_rel), float(beta_rel), float(tau_l))
        #clamp true grades
        clamped_true_grades = CalibrationBase.convertGradeScale(clamped_true_grades)
        clamped_values = { 'true_grades' : clamped_true_grades}
        #set reported grades 
        reported_grades = np.expand_dims(observed_grades, axis=0)
        reported_grades = CalibrationBase.convertGradeScale(reported_grades)
        _, efforts_samples, reliabilities_samples = run_gibbs(
            reported_grades,
            graph,
            hyperparams, 
            max_error=0, 
            clamped_values=clamped_values, 
            num_samples=1000,
            grade_scale='5',
            save_effort_draws=False,
            verbose=False,
        )
        dependability_samples = efforts_samples * reliabilities_samples
        dependability_lbs = np.quantile(dependability_samples[100:], 0.2, axis=0)
        return dependability_lbs
