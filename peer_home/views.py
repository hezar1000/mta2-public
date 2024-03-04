
from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
from django.shortcuts import render as djangoRender
from django.http import JsonResponse
from django.contrib import messages
import random
import numpy as np


from itertools import chain

from peer_home.wrappers import render
from peer_course.models import Course, CourseMember, CourseParticipation
from peer_course.decorators import chosen_course_required
from peer_course.base import CourseBase
from peer_assignment.models import Assignment
from peer_assignment.base import AssignmentBase
from peer_review.models import AssignmentWithReviews, ReviewAssignment
from peer_review.base import ReviewBase
from peer_evaluation.base import EvaluationBase
from peer_evaluation.models import EvaluationAssignment
from peer_grade.base import AppealBase, FlagBase
from peer_calibration.base import CalibrationBase
from django.views.decorators.csrf import csrf_exempt
from peer_review.base import ReviewBase
from peer_review.models import *
from django.contrib.auth.models import User
from peer_grade.models import Appeal, InaptReport
from peer_review.base import ReviewBase
from peer_review.models import *
from peer_course.base import CoursePermissions

# Functions other than view functions should be placed elsewhere

from peer_lecture.views import *

import datetime
from datetime import timedelta

class HomeViews:
    @staticmethod
    def render(request):
        "Render the homepage"

        render_dict = {"logged_in": request.user.is_authenticated}
        if request.user.is_authenticated:
            # We actually have a good enough dashboard in course_list
            return HomeViews.dashboard(request)
            # render_dict['pending_assignments'] = (AssignmentBase
            #     .get_user_assignments_by_status(request.user)['pending'])
            # render_dict['reviews'] = ReviewBase.get_user_review_by_status(request.user)
            # return render(request, 'dashboard.html', render_dict)
        # return djangoRender(request, 'index.html', render_dict)

        # return HttpResponseRedirect(reverse(settings.LOGIN_URL))
        return HttpResponseRedirect(reverse(settings.LOGIN_URL))

    @staticmethod
    def _ta_stats(ta, course):
        return dict(
            name=ta.get_user_fullname(),
            reviews=dict(
                pending=ta.get_pending_reviews()
                .filter(submission__assignment__course=course, submission__calibration_id=0)
                .count(),
                total=ta.reviewassignment_set.filter(
                    submission__assignment__course=course, submission__calibration_id=0
                ).count(),
                late=[
                    1
                    for ra in ta.get_pending_reviews().filter(
                        submission__assignment__course=course, submission__calibration_id=0
                    )
                    if ra.deadline_passed()
                ],
            ),
            appeal=dict(
                pending=ta.get_pending_apeals()
                .filter(submission__assignment__course=course)
                .count(),
                total=ta.appeal_set.filter(
                    submission__assignment__course=course
                ).count(),
            ),
            #time_spent= str(datetime.timedelta(seconds=round(ta.total_time))),
        )

    @staticmethod
    def student_todos(request, course, coursemember, render_dict):
        render_dict["is_independent"] = CourseBase.is_independent(
            request.user, course.id
        )
        render_dict["total_points"] = CalibrationBase.calibration_total_score(
            request.user, course
        )

        review_list = ReviewBase.get_my_reviews(request.user, course, "pending")
        assignment_list = [
            assignment
            for assignment in AssignmentBase.get(request.user, course, "pending")
            if assignment.can_compose_submission(coursemember)
        ]
        todo_items = sorted(
            chain(assignment_list, review_list),
            key=lambda instance: call_if_callable(instance.deadline),
        )
        return todo_items

    @staticmethod
    def staff_todos(request, course, coursemember, render_dict):

        render_dict["num_students"] = str(
            CourseMember._default_manager.filter(
                course=course, role="student", active=True
            ).count()
        )
        render_dict["num_independent"] = str(
            CourseMember._default_manager.filter(
                course=course, is_independent=True, role="student", active=True
            ).count()
        )
        render_dict["num_supervised"] = str(
            CourseMember._default_manager.filter(
                course=course, is_independent=False, role="student", active=True
            ).count()
        )

        review_list = ReviewBase.get_my_reviews(request.user, course, "pending")
        evaluation_list = EvaluationBase.get_my_evaluations(
            request.user, course, "pending"
        )
        appeal_list = AppealBase.find_pending_by_assignee(request.user, course.id)
        report_list = FlagBase.find_pending_by_assignee(request.user, course.id)
        todo_items = (
            list(report_list)
            + list(appeal_list)
            + sorted(
                chain(review_list, evaluation_list),
                key=lambda instance: instance.deadline(),
            )
        )
        if CourseBase.is_instructor(request.user, course.id) or CourseBase.is_ta(request.user, course.id):
            render_dict["ta_stats"] = [
                HomeViews._ta_stats(ta, course) for ta in course.tas()
            ]

        return todo_items

    @staticmethod
    @chosen_course_required
    def dashboard(request):
        render_dict = dict()

        cid = request.session["course_id"]
        course = Course._default_manager.get(id=cid)
        request.session["course_id"] = course.id
        request.session['course_role'] = course.id
        
        if request.method == 'POST':
            if 'begin-lecture' in request.POST:
                render_dict['lecture'] = "true"
                PollViews.instructor(request)
                MessageViews.instructor(request)
            elif 'end-lecture' in request.POST:
                PollViews.instructor(request)
                MessageViews.instructor(request)
        
        current_lecture = Lecture.currentLecture(course.id)
        
        if current_lecture:
            render_dict['lecture'] = current_lecture

        if "next" in request.GET:
            return HttpResponseRedirect(request.GET["next"])
        
        if course.enable_participation == False: 
            render_dict["course"] = course

            coursemember = CourseBase.get_course_member(request.user, course.id)

            if CourseBase.is_course_staff(request.user, cid):
                render_dict["todos"] = HomeViews.staff_todos(
                    request, course, coursemember, render_dict
                )
                render_dict["total_reviews"] = ReviewAssignment._default_manager.filter(
                    submission__assignment__course= course,
                    grader__role= 'ta',
                    submitted= True,
                    submission__calibration_id=0
                ).count()
                render_dict["user_total_reviews"] =  ReviewAssignment._default_manager.filter(
                    submission__assignment__course= course,
                    grader__user= request.user,
                    submitted= True,
                    submission__calibration_id=0
                ).count()
            elif CourseBase.is_course_member(request.user, cid):
                render_dict["todos"] = HomeViews.student_todos(
                    request, course, coursemember, render_dict
                )

            render_dict["grade_items"] = EvaluationBase.get_my_grades(request.user, course)
            # print(render_dict['submissions'])

            if not request.user.is_superuser:
                render_dict["coursemember"] = coursemember
                render_dict["dependability_min"]= round(coursemember.lower_confidence_bound,3)
                render_dict["dependability_mean"]= round(coursemember.markingload,3)
                render_dict["dependability_max"]= round(coursemember.upper_confidence_bound,3)


    #            render_dict["dependability_min"]= round(CalibrationBase.convert_dependability_to_grade(coursemember.lower_confidence_bound),3)
    #            render_dict["dependability_mean"]= round(CalibrationBase.convert_dependability_to_grade(coursemember.markingload),3)
    #            render_dict["dependability_max"]= round(CalibrationBase.convert_dependability_to_grade(coursemember.upper_confidence_bound),3)
            if coursemember.role == 'ta':
                # inapt_reports = InaptReport.objects.filter(assignee__id=coursemember.id)
                # inapt_timer = sum([x.timer for x in inapt_reports])
                # appeals = Appeal.objects.filter(assignee__id=coursemember.id)
                # appeal_time = sum([x.timer for x in appeals])
                # reviews = ReviewAssignment.objects.filter(grader__id=coursemember.id)
                # review_time = sum([x.timer for x in reviews])
                # evaluations = EvaluationAssignment.objects.filter(grader__id=coursemember.id)
                # evaluation_time = sum([x.timer for x in evaluations])
                # time = round(appeal_time + review_time + inapt_timer + evaluation_time)
                # render_dict["timer"] = str(datetime.timedelta(seconds=time))
                participations = CourseParticipation.objects.filter(participant = coursemember).order_by('-id')
                ending_participations = participations.filter(participation_list = 11)
                timer = timedelta(seconds = 0)
                for participation in ending_participations:
                    starting_participation  = participations[list(participations).index(participation)+1]
                    if starting_participation.participation_list == 10:
                        time_spent = participation.time_participated - starting_participation.time_participated
                        if time_spent > timedelta(seconds = 0):
                            timer += time_spent
                render_dict["timer"] = str(timer)
                    
            return render(request, "course-view-redesign.html", render_dict)

        else:
            # render_dict["course"] = course
            # time_of_request = timezone.now()
            # coursemember = CourseBase.get_course_member(request.user, course.id)
            # render_dict["coursemember"] = coursemember
            # participations = CourseParticipation.objects.filter(
            #     participant = coursemember,
            #     count_in_calculations = True
            # )
            # participations_today = participations.filter(time_participated__startswith = time_of_request.date())
            # green_points = 0 
            # blue_points = 0
            # red_points = 0
            # yellow_points = 0
            # total_points = 0 
            # total_points_today = 0
            # for participation in participations.filter(participation_list=1):
            #     green_points += participation.participation_points_gained
            #     total_points += participation.participation_points_gained
            # for participation in participations.filter(participation_list=2):
            #     blue_points += participation.participation_points_gained
            #     total_points += participation.participation_points_gained
            # for participation in participations.filter(participation_list=3):
            #     red_points += participation.participation_points_gained
            #     total_points += participation.participation_points_gained
            # for participation in participations.filter(participation_list=4):
            #     yellow_points += participation.participation_points_gained
            #     total_points += participation.participation_points_gained

            # for participation in participations_today:
            #     total_points_today += participation.participation_points_gained

                
            # render_dict["green_points"]= green_points
            # render_dict["blue_points"]= blue_points
            # render_dict["red_points"]= red_points
            # render_dict["yellow_points"]= yellow_points
            # render_dict["total_points"]= total_points
            # render_dict["total_points_today"]= total_points_today

            render_dict["course"] = course

            coursemember = CourseBase.get_course_member(request.user, course.id)

            if CourseBase.is_course_staff(request.user, cid):
                render_dict["todos"] = HomeViews.staff_todos(
                    request, course, coursemember, render_dict
                )
                render_dict["total_reviews"] = ReviewAssignment._default_manager.filter(
                    submission__assignment__course= course,
                    grader__role= 'ta',
                    submitted= True,
                    submission__calibration_id=0
                ).count()
                render_dict["user_total_reviews"] =  ReviewAssignment._default_manager.filter(
                    submission__assignment__course= course,
                    grader__user= request.user,
                    submitted= True,
                    submission__calibration_id=0
                ).count()
            elif CourseBase.is_course_member(request.user, cid):
                render_dict["todos"] = HomeViews.student_todos(
                    request, course, coursemember, render_dict
                )

            render_dict["grade_items"] = EvaluationBase.get_my_grades(request.user, course)
            # print(render_dict['submissions'])

            if not request.user.is_superuser:
                render_dict["coursemember"] = coursemember
                render_dict["dependability_min"]= round(coursemember.lower_confidence_bound,3)
                render_dict["dependability_mean"]= round(coursemember.markingload,3)
                render_dict["dependability_max"]= round(coursemember.upper_confidence_bound,3)


    #            render_dict["dependability_min"]= round(CalibrationBase.convert_dependability_to_grade(coursemember.lower_confidence_bound),3)
    #            render_dict["dependability_mean"]= round(CalibrationBase.convert_dependability_to_grade(coursemember.markingload),3)
    #            render_dict["dependability_max"]= round(CalibrationBase.convert_dependability_to_grade(coursemember.upper_confidence_bound),3)
            if coursemember.role == 'ta':
                # inapt_reports = InaptReport.objects.filter(assignee__id=coursemember.id)
                # inapt_timer = sum([x.timer for x in inapt_reports])
                # appeals = Appeal.objects.filter(assignee__id=coursemember.id)
                # appeal_time = sum([x.timer for x in appeals])
                # reviews = ReviewAssignment.objects.filter(grader__id=coursemember.id)
                # review_time = sum([x.timer for x in reviews])
                # evaluations = EvaluationAssignment.objects.filter(grader__id=coursemember.id)
                # evaluation_time = sum([x.timer for x in evaluations])
                # time = round(appeal_time + review_time + inapt_timer + evaluation_time)
                # render_dict["timer"] = str(datetime.timedelta(seconds=time))
                participations = CourseParticipation.objects.filter(participant = coursemember).order_by('-id')
                ending_participations = participations.filter(participation_list = 11)
                timer = timedelta(seconds = 0)
                for participation in ending_participations:
                    starting_participation  = participations[list(participations).index(participation)+1]
                    if starting_participation.participation_list == 10:
                        time_spent = participation.time_participated - starting_participation.time_participated
                        if time_spent > timedelta(seconds = 0):
                            timer += time_spent
                render_dict["timer"] = str(timer)

            return render(request, "course-view.html", render_dict)        

    @staticmethod
    def random_student_helper(request, lid):
        # lid = int(lid)
        # if lid == 1 or lid ==2:
        #     list_lid = [1,2]
        # elif lid ==3:
        #     list_lid = [3]

        cid = request.session["course_id"]
        CoursePermissions.require_instructor(request.user, cid)
        render_dict = dict()
        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        time_of_request = timezone.now()

        lid = int(lid)
        list_lid = []
        if not course.points_upon_participation_in_green_list == 0:
            list_lid.append(1)
        if not course.points_upon_participation_in_blue_list == 0:
            list_lid.append(2)
        if not course.points_upon_participation_in_red_list == 0:
            list_lid.append(3)
        if not course.points_upon_participation_in_yellow_list == 0:
            list_lid.append(4)

        if lid == 1 and course.points_upon_participation_in_green_list == 0:
            list_lid = [1]
        if lid == 2 and course.points_upon_participation_in_blue_list == 0:
            list_lid = [2]
        if lid == 3 and course.points_upon_participation_in_red_list == 0:
            list_lid = [3]
        if lid == 3 and course.points_upon_participation_in_yellow_list == 0:
            list_lid = [4]


        if lid ==1:
            color = 'Green'
            students = CourseMember.objects.filter(course = course, hand_up= True
                ,role='student', active= True)
            activate = coursemember.hand_up 
            participation_points_to_gain = course.points_upon_participation_in_green_list
        if lid ==2:
            color = 'Blue'
            students = CourseMember.objects.filter(course = course, hand_up_list_2= True
                ,role='student', active= True)
            activate = coursemember.hand_up_list_2
            participation_points_to_gain = course.points_upon_participation_in_blue_list
        if lid ==3: 
            color = 'Red'
            students = CourseMember.objects.filter(course = course, hand_up_list_3= True
                ,role='student', active= True)
            activate = coursemember.hand_up_list_3
            participation_points_to_gain = course.points_upon_participation_in_red_list
        if lid ==4: 
            color = 'Yellow'
            students = CourseMember.objects.filter(course = course, hand_up_list_4= True
                ,role='student', active= True)
            activate = coursemember.hand_up_list_4
            participation_points_to_gain = course.points_upon_participation_in_yellow_list

        if coursemember.role == 'instructor':
            if activate == False:
                render_dict['student'] = "You should enable the hand up feature for the "+color+" list first."
                render_dict['student_id']= 'None'
                return JsonResponse(render_dict)

            all_participations = CourseParticipation.objects.filter(
                participant__in = students,
                participation_list__in = list_lid,
                count_in_calculations = True
            )

            std_participations = all_participations.filter(
                time_participated__startswith = time_of_request.date(),
            )
            if students.exists():
                list_of_spoken= []
                list_of_unspoken=[]
                list_of_spoken_counts= []
                list_of_unspoken_counts= []
                for student in students:
                    std_participation = std_participations.filter(participant = student)
                    if not std_participation.exists():
                        CourseParticipation.objects.create(
                            participant  = student, 
                            time_participated = time_of_request,
                            participation_points_gained = participation_points_to_gain,
                            spoke_upon_participation = False,
                            participation_list= lid
                        )
                    else:
                        CourseParticipation.objects.create(
                            participant  = student, 
                            time_participated = time_of_request,
                            participation_points_gained = participation_points_to_gain * course.fraction_of_points_gained_upon_further_participations ,
                            participation_list= lid
                        )

                    spoken_participations = std_participations.filter(participant= student, spoke_upon_participation = True, participation_list__in= list_lid )
                    spoken_count = all_participations.filter(participant= student, spoke_upon_participation = True, participation_list__in= list_lid).count()
                    spoken_count = spoken_count if spoken_count > 1 else 2

                    if spoken_participations.exists() and student not in list_of_spoken:
                        list_of_spoken.append(student)
                        list_of_spoken_counts.append(1/np.log2(spoken_count))
                    if not spoken_participations.exists() and student not in list_of_unspoken:
                        list_of_unspoken.append(student)
                        list_of_unspoken_counts.append(1/np.log2(spoken_count))


                list_of_spoken_counts= np.array(list_of_spoken_counts)
                list_of_unspoken_counts= np.array(list_of_unspoken_counts)


                list_of_spoken_counts_norm = list_of_spoken_counts/sum(list_of_spoken_counts)
                list_of_unspoken_counts_norm = list_of_unspoken_counts/sum(list_of_unspoken_counts)

                    
                if list_of_unspoken:
                    unspoken_student = np.random.choice(list_of_unspoken, p = list_of_unspoken_counts_norm)

                    # unspoken_student = random.choice(list_of_unspoken)
                    render_dict['student']= unspoken_student.user.first_name +' '+unspoken_student.user.last_name
                    render_dict['student_id']= unspoken_student.user.username

                    if lid == 1:
                        unspoken_student.hand_up = False
                    elif lid == 2:
                        unspoken_student.hand_up_list_2 = False
                    elif lid == 3:
                        unspoken_student.hand_up_list_3 = False
                    elif lid == 4:
                        unspoken_student.hand_up_list_4 = False
                    unspoken_student.save()

                    participation = CourseParticipation.objects.get(
                        participant = unspoken_student,
                        time_participated = time_of_request
                    )
                    participation.spoke_upon_participation = True
                    participation.save()
                    
                elif list_of_spoken:
                    # spoken_students = students_to_speak.filter(spoken='True').order_by('?')
                    
                        # for std in spoken_students:
                        #     list_of_spoken.append(std.user.first_name +' '+std.user.last_name)
                        spoken_student = np.random.choice(list_of_spoken, p = list_of_spoken_counts_norm)

                        # spoken_student = random.choice(list_of_spoken)
                        # spoken_student.hand_up = False
                        if lid == 1:
                            spoken_student.hand_up = False
                        elif lid ==2:
                            spoken_student.hand_up_list_2 = False
                        elif lid ==3:
                            spoken_student.hand_up_list_3 = False
                        elif lid ==4:
                            spoken_student.hand_up_list_4 = False
                        spoken_student.save()

                        render_dict['student']= spoken_student.user.first_name +' '+spoken_student.user.last_name
                         
                        render_dict['student_id']= spoken_student.user.username
                        participation = CourseParticipation.objects.get(
                            participant = spoken_student,
                            time_participated = time_of_request   
                        )
                        participation.spoke_upon_participation = True
                        participation.save()

                participations_to_consider = CourseParticipation.objects.filter(
                    participant__course = course,
                    time_participated__startswith = time_of_request.date(),
                    spoke_upon_participation= True,
                    participation_list__in = list_lid,
                    count_in_calculations = True
                )

                students_for_bonus_credit = list(participations_to_consider.values_list('participant',flat= True).distinct())


                for std_id in students_for_bonus_credit:
                    if  not CourseParticipation.objects.filter(
                            participant_id  = std_id, 
                            time_participated = time_of_request,
                            participation_list= lid,
                            count_in_calculations = True
                        ).exists():
                        date_first_class_ends = timezone.now()
                        new_time = date_first_class_ends.replace(hour =22, minute = 00)
                        # if participations_to_consider.filter(participant_id  = std_id, time_participated__lte = new_time).exists() and timezone.now().time() > datetime.time(22, 00, 00, 000000):
                        if False:
                            CourseParticipation.objects.create(
                                participant_id  = std_id, 
                                time_participated = time_of_request,
                                participation_points_gained = participation_points_to_gain * course.fraction_of_points_gained_upon_further_participations,
                                spoke_upon_participation = False,
                                participation_list= lid,
                                real_participation = False,
                                count_in_calculations = False
                            )
                        else:
                            CourseParticipation.objects.create(
                                participant_id  = std_id, 
                                time_participated = time_of_request,
                                participation_points_gained = participation_points_to_gain * course.fraction_of_points_gained_upon_further_participations,
                                spoke_upon_participation = False,
                                participation_list= lid,
                                real_participation = False,
                                count_in_calculations = True
                            )

            else:
                render_dict['student']= 'No available student in the '+color+' list.'
                render_dict['student_id']= 'None'
        else:
            render_dict['student']= 'You are not an instructor in this course.'
        return JsonResponse(render_dict) 


    @staticmethod
    @login_required
    @chosen_course_required
    def random_student(request):
        return HomeViews.random_student_helper(request, 1)

    @staticmethod
    @login_required
    @chosen_course_required
    def random_student_blue(request):
        return HomeViews.random_student_helper(request, 2)


    @staticmethod
    @login_required
    @chosen_course_required
    def random_student_red(request):
        return HomeViews.random_student_helper(request, 3)

    @staticmethod
    @login_required
    @chosen_course_required
    def random_student_yellow(request):
        return HomeViews.random_student_helper(request, 4)

    @staticmethod
    @login_required
    @chosen_course_required
    def choose_next(request, uid, lid):

        cid = request.session["course_id"]
        CoursePermissions.require_instructor(request.user, cid)
        render_dict = dict()
        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        chosen_student = CourseMember.objects.filter(id=uid)
        time_of_request = timezone.now()

        lid = int(lid)
        list_lid = []
        if not course.points_upon_participation_in_green_list == 0:
            list_lid.append(1)
        if not course.points_upon_participation_in_blue_list == 0:
            list_lid.append(2)
        if not course.points_upon_participation_in_red_list == 0:
            list_lid.append(3)
        if not course.points_upon_participation_in_yellow_list == 0:
            list_lid.append(4)

        if lid == 1 and course.points_upon_participation_in_green_list == 0:
            list_lid = [1]
        if lid == 2 and course.points_upon_participation_in_blue_list == 0:
            list_lid = [2]
        if lid == 3 and course.points_upon_participation_in_red_list == 0:
            list_lid = [3]
        if lid == 3 and course.points_upon_participation_in_yellow_list == 0:
            list_lid = [4]

        # if lid == 1 or lid ==2:
        #     list_lid = [1,2]
        # elif lid ==3:
        #     list_lid = [3]

        if coursemember.role == 'instructor':
            if coursemember.hand_up == False:
                render_dict['student'] = "You should enable the hand up feature for the Green list first."
                render_dict['student_id']= 'None'
                return JsonResponse(render_dict)

            if lid == 1 : 
                students = CourseMember.objects.filter(course = course, hand_up= True
                    ,role='student', active= True) 
                participation_points_to_gain = course.points_upon_participation_in_green_list
                color = 'Green'

            elif lid == 2:
                students = CourseMember.objects.filter(course = course, hand_up_list_2= True
                    ,role='student', active= True) 
                participation_points_to_gain = course.points_upon_participation_in_blue_list
                color = 'Blue'
            elif lid == 3: 
                students = CourseMember.objects.filter(course = course, hand_up_list_3= True
                    ,role='student', active= True) 
                participation_points_to_gain = course.points_upon_participation_in_red_list
                color = 'Red'
            elif lid == 4: 
                students = CourseMember.objects.filter(course = course, hand_up_list_4= True
                    ,role='student', active= True) 
                participation_points_to_gain = course.points_upon_participation_in_yellow_list
                color = 'Yellow'

            if students.exists():
                for student in students:
                    if not CourseParticipation.objects.filter(
                        participant = student,
                        time_participated__startswith = time_of_request.date(),
                        participation_list__in = list_lid,
                        count_in_calculations = True
                    ).exists():
                        # student.participation_points += 10
                        # student.first_hand_up = False
                        # student.save()
                        CourseParticipation.objects.create(
                            participant  = student, 
                            time_participated = time_of_request,
                            participation_points_gained = participation_points_to_gain,
                            spoke_upon_participation = False,
                            participation_list= lid
                        )
                    # elif student.hand_up == True and student.first_hand_up == False:
                    else:
                        # student.participation_points += 1
                        # student.save()
                        CourseParticipation.objects.create(
                            participant  = student, 
                            time_participated = time_of_request,
                            participation_points_gained = participation_points_to_gain * course.fraction_of_points_gained_upon_further_participations,
                            participation_list= lid
                        )


                participations_to_consider = CourseParticipation.objects.filter(
                    participant__course = course,
                    time_participated__startswith = time_of_request.date(),
                    spoke_upon_participation= True,
                    participation_list__in = list_lid,
                    count_in_calculations = True
                )

                students_for_bonus_credit = list(participations_to_consider.values_list('participant',flat= True).distinct())


                for std_id in students_for_bonus_credit:
                    if  not CourseParticipation.objects.filter(
                            participant_id  = std_id, 
                            time_participated = time_of_request,
                            participation_list= lid,
                            count_in_calculations = True
                        ).exists():
                        date_first_class_ends = timezone.now()
                        date_first_class_ends.replace(hour =22, minute = 00)
                        # if participations_to_consider.filter(participant_id  = std_id, time_participated__lte = date_first_class_ends).exists() and timezone.now().time() > datetime.time(22, 00, 00, 000000):
                        if False:
                            CourseParticipation.objects.create(
                                participant_id  = std_id, 
                                time_participated = time_of_request,
                                participation_points_gained = participation_points_to_gain * course.fraction_of_points_gained_upon_further_participations,
                                spoke_upon_participation = False,
                                participation_list= lid,
                                real_participation = False,
                                count_in_calculations = False
                            )
                        else:
                            CourseParticipation.objects.create(
                                participant_id  = std_id, 
                                time_participated = time_of_request,
                                participation_points_gained = participation_points_to_gain * course.fraction_of_points_gained_upon_further_participations,
                                spoke_upon_participation = False,
                                participation_list= lid,
                                real_participation = False,
                                count_in_calculations = True
                            )

            
            students_to_speak = chosen_student
            # list_of_spoken= []
            # list_of_unspoken=[]
            if students_to_speak.exists():
                if not CourseParticipation.objects.filter(
                        participant = chosen_student[0],
                        time_participated__startswith = time_of_request.date(),
                        participation_list = lid,
                        spoke_upon_participation = True,
                        count_in_calculations = True
                    ).exists():
                    unspoken_student = chosen_student[0]
                    render_dict['student']= unspoken_student.user.first_name +' '+unspoken_student.user.last_name
                    render_dict['color'] = color
                    render_dict['student_id']= unspoken_student.user.username
                    print (render_dict)
                    # unspoken_student.spoken= True
                    # unspoken_student.time_spoken = time_of_request

                    if lid == 1:
                        unspoken_student.hand_up = False
                    elif lid ==2:
                        unspoken_student.hand_up_list_2 = False
                    elif lid ==3:
                        unspoken_student.hand_up_list_3 = False
                    elif lid ==4:
                        unspoken_student.hand_up_list_4 = False
                    unspoken_student.save()

                    new_participation = CourseParticipation.objects.get(
                        participant = unspoken_student,
                        time_participated = time_of_request
                    )
                    new_participation.spoke_upon_participation = True
                    new_participation.save()
                    
                else:
                    # spoken_students = students_to_speak.filter(spoken='True').order_by('?')
                    spoken_students = chosen_student
                    if spoken_students.exists():
                        # for std in spoken_students:
                        #     list_of_spoken.append(std.user.first_name +' '+std.user.last_name)
                        spoken_student= spoken_students[0]
                        # spoken_student.hand_up = False
                        if lid == 1:
                            spoken_student.hand_up = False
                        elif lid ==2:
                            spoken_student.hand_up_list_2 = False
                        elif lid ==3:
                            spoken_student.hand_up_list_3 = False
                        elif lid ==4:
                            spoken_student.hand_up_list_4 = False
                        spoken_student.save()

                        render_dict['student']= spoken_student.user.first_name +' '+spoken_student.user.last_name
                        render_dict['color'] = color
                        render_dict['student_id']= spoken_student.user.username
                        new_participation = CourseParticipation.objects.get(
                            participant = spoken_student,
                            time_participated = time_of_request   
                        )
                        new_participation.spoke_upon_participation = True
                        new_participation.save()

            # else:
            #     render_dict['student']= 'No available student in the Green list.'
            #     render_dict['student_id']= 'None'

            # render_dict['list_of_unspoken'] = list_of_unspoken
            # render_dict['list_of_spoken'] = list_of_spoken
        else:
            render_dict['student']= 'You are not an instructor in this course.'
   
        return JsonResponse(render_dict) 



    @staticmethod
    @login_required
    @chosen_course_required
    def clear_all(request):
        cid = request.session["course_id"]
        CoursePermissions.require_instructor(request.user, cid)
        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        if coursemember.role == 'instructor':
            students = CourseMember.objects.filter(course = course, hand_up= True, 
                role='student', active= True)

            for student in students:
                student.hand_up = False
                student.save()

        return HttpResponse('hands were cleared out.')

    @staticmethod
    @login_required
    @chosen_course_required
    def clear_all_lists(request):

        cid = request.session["course_id"]
        CoursePermissions.require_course_member(request.user, cid)
        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)

        if coursemember.role == "instructor":
            students = CourseMember.objects.filter(course = course, role='student', hand_up= True, active= True) | CourseMember.objects.filter(course = course, role='student', hand_up_list_2= True, active= True) | CourseMember.objects.filter(course = course, role='student', hand_up_list_3= True, active= True) | CourseMember.objects.filter(course = course, role='student', hand_up_list_4= True, active= True)
            for student in students:
                student.hand_up= False
                student.hand_up_list_2= False
                student.hand_up_list_3= False
                student.hand_up_list_4= False
                student.save()

        return HttpResponse('hands were cleared out.')

    @staticmethod
    @login_required
    @chosen_course_required
    def clear_all_blue(request):
        cid = request.session["course_id"]
        CoursePermissions.require_instructor(request.user, cid)
        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        if coursemember.role == 'instructor':
            students = CourseMember.objects.filter(course = course, hand_up_list_2= True, 
                role='student', active= True)

            for student in students:
                student.hand_up_list_2 = False
                student.save()

        return HttpResponse('Blue hands were cleared out.')

    @staticmethod
    @login_required
    @chosen_course_required
    def clear_all_red(request):
        cid = request.session["course_id"]
        CoursePermissions.require_instructor(request.user, cid)
        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        if coursemember.role == 'instructor':
            students = CourseMember.objects.filter(course = course, hand_up_list_3= True, 
                role='student', active= True)

            for student in students:
                student.hand_up_list_3 = False
                student.save()

        return HttpResponse('Red hands were cleared out.')


    @staticmethod
    @login_required
    @chosen_course_required
    def clear_all_yellow(request):
        cid = request.session["course_id"]
        CoursePermissions.require_instructor(request.user, cid)
        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        if coursemember.role == 'instructor':
            students = CourseMember.objects.filter(course = course, hand_up_list_4= True, 
                role='student', active= True)

            for student in students:
                student.hand_up_list_4 = False
                student.save()

        return HttpResponse('Yellow hands were cleared out.')



    @staticmethod
    @login_required
    @chosen_course_required
    def enable(request):
        return HomeViews.enable_list_helper(request,1)
        # render_dict = dict()
        # cid = request.session["course_id"]
        # CoursePermissions.require_course_member(request.user, cid)
        # course = Course._default_manager.get(id=cid)
        # coursemember = CourseBase.get_course_member(request.user, course.id)

        # if coursemember.hand_up == False:

        #     if coursemember.role == "instructor":
        #         coursemember.hand_up = True
        #         coursemember.save()
        #         render_dict['hand']= 'The hand up feature is enabled for the Green list.'

        #     if coursemember.role == 'student':
        #         instructors = CourseMember.objects.filter(course = course, role= 'instructor')
        #         if instructors.exists():
        #             for instructor in instructors:
        #                 if instructor.hand_up == True:
        #                     coursemember.hand_up = True
        #                     coursemember.save()
        #                     render_dict['hand'] = 'Your hand is up in the Green list. '
        #                 else:
        #                     render_dict['hand'] = 'The Green list is disabled by the instructor for now.'
                            

        #     # return JsonResponse(render_dict)
        # else:
        #     pass
        #     # coursemember.hand_up = False
        #     # coursemember.save()
        #     # if coursemember.role == "instructor":
        #     #     students = CourseMember.objects.filter(course = course, hand_up= True, 
        #     #         role='student', active= True)
        #     #     for student in students:
        #     #         student.hand_up= False
        #     #         student.save()
        #     # render_dict['hand'] = 'hand up was disabled.'
        
        # return JsonResponse(render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def enable_blue(request):
        return HomeViews.enable_list_helper(request,2)

    @staticmethod
    @login_required
    @chosen_course_required
    def enable_red(request):
        return HomeViews.enable_list_helper(request,3)

    @staticmethod
    @login_required
    @chosen_course_required
    def enable_yellow(request):
        return HomeViews.enable_list_helper(request,4)

    @staticmethod
    @login_required
    @chosen_course_required
    def enable_all(request):
        cid = request.session["course_id"]
        CoursePermissions.require_course_member(request.user, cid)

        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)

        coursemember.hand_up = True
        coursemember.hand_up_list_2 = True
        coursemember.hand_up_list_3 = True
        coursemember.hand_up_list_4 = True
        coursemember.save()

        return HttpResponse('Hand up was enabled in all lists.')


    def enable_list_helper(request, lid):
        render_dict = dict()
        cid = request.session["course_id"]
        CoursePermissions.require_course_member(request.user, cid)
        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        if coursemember.role == "instructor":
            if lid == 1:
                coursemember.hand_up = True
                coursemember.save()
                color = 'Green'
            if lid == 2:
                coursemember.hand_up_list_2 = True
                coursemember.save()
                color = 'Blue'
            if lid == 3:
                coursemember.hand_up_list_3 = True
                coursemember.save()
                color = 'Red'

            if lid == 4:
                coursemember.hand_up_list_4 = True
                coursemember.save()
                color = 'Yellow'
  
        if coursemember.role == 'student':
            if coursemember.hand_up == True or coursemember.hand_up_list_2 == True or coursemember.hand_up_list_3 == True or coursemember.hand_up_list_4 == True:
                render_dict['hand'] = '<span style="color: red">  You can only raise your hand in one list at the time. </span>'
            else:
                if lid ==1:
                    instructors = CourseMember.objects.filter(course = course, role= 'instructor')
                    if instructors.exists():
                        for instructor in instructors:
                            if instructor.hand_up == True:
                                coursemember.hand_up= True
                                coursemember.save()
                                render_dict['hand'] = 'Your hand is up in the Green list. '
                            else:
                                render_dict['hand'] = 'The Green list is disabled by the instructor for now.'
                                
                if lid ==2:
                    instructors = CourseMember.objects.filter(course = course, role= 'instructor')
                    if instructors.exists():
                        for instructor in instructors:
                            if instructor.hand_up_list_2 == True:
                                coursemember.hand_up_list_2 = True
                                coursemember.save()
                                render_dict['hand'] = 'Your hand is up in the Blue list. '
                            else:
                                render_dict['hand'] = 'The Blue list is disabled by the instructor for now.'
                            
                if lid ==3: 
                    instructors = CourseMember.objects.filter(course = course, role= 'instructor')
                    if instructors.exists():
                        for instructor in instructors:
                            if instructor.hand_up_list_3 == True:
                                coursemember.hand_up_list_3 = True
                                coursemember.save()
                                render_dict['hand'] = 'Your hand is up in the Red list. '
                            else:
                                render_dict['hand'] = 'The Red list is disabled by the instructor for now.'
                            
                if lid ==4: 
                    instructors = CourseMember.objects.filter(course = course, role= 'instructor')
                    if instructors.exists():
                        for instructor in instructors:
                            if instructor.hand_up_list_4 == True:
                                coursemember.hand_up_list_4 = True
                                coursemember.save()
                                render_dict['hand'] = 'Your hand is up in the Yellow list. '
                            else:
                                render_dict['hand'] = 'The Yellow list is disabled by the instructor for now.'
                            
        return JsonResponse(render_dict)

    # @staticmethod
    # @login_required
    # @chosen_course_required
    # def disable(request):
    #     cid = request.session["course_id"]
    #     CoursePermissions.require_course_member(request.user, cid)

    #     course = Course._default_manager.get(id=cid)
    #     coursemember = CourseBase.get_course_member(request.user, course.id)
        
    #     coursemember.hand_up = False
    #     coursemember.save()

    #     if coursemember.role == "instructor":
    #         students = CourseMember.objects.filter(course = course, hand_up= True, 
    #             role='student', active= True)
    #         for student in students:
    #             student.hand_up= False
    #             student.save()

    #     return HttpResponse('hand up was disabled.')


    # @staticmethod
    # @login_required
    # @chosen_course_required
    # def enable_blue(request):
    #     render_dict = dict()
    #     cid = request.session["course_id"]
    #     CoursePermissions.require_course_member(request.user, cid)
    #     course = Course._default_manager.get(id=cid)
    #     coursemember = CourseBase.get_course_member(request.user, course.id)
        
    #     if coursemember.role == "instructor":
    #         coursemember.hand_up_list_2 = True
    #         coursemember.save()
    #         render_dict['hand']= 'The hand up feature is enabled for the Blue list.'
            
    #     if coursemember.role == 'student':
    #         instructors = CourseMember.objects.filter(course = course, role= 'instructor')
    #         if instructors.exists():
    #             for instructor in instructors:
    #                 if instructor.hand_up_list_2 == True:
    #                     coursemember.hand_up_list_2 = True
    #                     coursemember.save()
    #                     render_dict['hand'] = 'Your hand is up in the Blue list. '
    #                 else:
    #                     render_dict['hand'] = 'The Blue list is disabled by the instructor for now.'
                         

    #     return JsonResponse(render_dict)


    # @staticmethod
    # @login_required
    # @chosen_course_required
    # def enable_red(request):
    #     render_dict = dict()
    #     cid = request.session["course_id"]
    #     CoursePermissions.require_course_member(request.user, cid)
    #     course = Course._default_manager.get(id=cid)
    #     coursemember = CourseBase.get_course_member(request.user, course.id)
        
    #     if coursemember.role == "instructor":
    #         coursemember.hand_up_list_3 = True
    #         coursemember.save()
    #         render_dict['hand']= 'The hand up feature is enabled for the Red list.'
            
    #     if coursemember.role == 'student':
    #         instructors = CourseMember.objects.filter(course = course, role= 'instructor')
    #         if instructors.exists():
    #             for instructor in instructors:
    #                 if instructor.hand_up_list_3 == True:
    #                     coursemember.hand_up_list_3 = True
    #                     coursemember.save()
    #                     render_dict['hand'] = 'Your hand is up in the Red list. '
    #                 else:
    #                     render_dict['hand'] = 'The Red list is disabled by the instructor for now.'
                         

    #     return JsonResponse(render_dict)

    @staticmethod
    @login_required
    @chosen_course_required
    def disable(request):
        cid = request.session["course_id"]
        CoursePermissions.require_course_member(request.user, cid)

        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        
        coursemember.hand_up = False
        coursemember.save()

        if coursemember.role == "instructor":
            students = CourseMember.objects.filter(course = course, hand_up= True, 
                role='student', active= True)
            for student in students:
                student.hand_up= False
                student.save()

        return HttpResponse('hand up was disabled.')

    @staticmethod
    @login_required
    @chosen_course_required
    def disable_blue(request):
        cid = request.session["course_id"]
        CoursePermissions.require_course_member(request.user, cid)

        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        
        coursemember.hand_up_list_2 = False
        coursemember.save()

        if coursemember.role == "instructor":
            students = CourseMember.objects.filter(course = course, hand_up_list_2= True, 
                role='student', active= True)
            for student in students:
                student.hand_up_list_2= False
                student.save()

        return HttpResponse('hand up was disabled for the Blue list.')

    @staticmethod
    @login_required
    @chosen_course_required
    def disable_red(request):
        cid = request.session["course_id"]
        CoursePermissions.require_course_member(request.user, cid)

        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        
        coursemember.hand_up_list_3 = False
        coursemember.save()

        if coursemember.role == "instructor":
            students = CourseMember.objects.filter(course = course, hand_up_list_3= True, 
                role='student', active= True)
            for student in students:
                student.hand_up_list_3= False
                student.save()

        return HttpResponse('hand up was disabled for the Red list.')

    @staticmethod
    @login_required
    @chosen_course_required
    def disable_yellow(request):
        cid = request.session["course_id"]
        CoursePermissions.require_course_member(request.user, cid)

        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        
        coursemember.hand_up_list_4 = False
        coursemember.save()

        if coursemember.role == "instructor":
            students = CourseMember.objects.filter(course = course, hand_up_list_4= True, 
                role='student', active= True)
            for student in students:
                student.hand_up_list_4= False
                student.save()

        return HttpResponse('hand up was disabled for the Yellow list.')


    @staticmethod
    @login_required
    @chosen_course_required
    def disable_all(request):
        cid = request.session["course_id"]
        CoursePermissions.require_course_member(request.user, cid)

        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)

        coursemember.hand_up = False
        coursemember.hand_up_list_2 = False
        coursemember.hand_up_list_3 = False
        coursemember.hand_up_list_4 = False
        coursemember.save()

        if coursemember.role == "instructor":
            students = CourseMember.objects.filter(course = course, role='student', hand_up= True, active= True) | CourseMember.objects.filter(course = course, role='student', hand_up_list_2= True, active= True) | CourseMember.objects.filter(course = course, role='student', hand_up_list_3= True, active= True) | CourseMember.objects.filter(course = course, role='student', hand_up_list_4= True, active= True)
            for student in students:
                student.hand_up= False
                student.hand_up_list_2= False
                student.hand_up_list_3= False
                student.hand_up_list_4= False
                student.save()

        return HttpResponse('Hand up was disabled in all lists.')



    @staticmethod
    @login_required
    @chosen_course_required
    def check_status(request):
        render_dict = dict()
        cid = request.session["course_id"]
        course = Course._default_manager.get(id=cid)
        CoursePermissions.require_course_member(request.user, cid)
        coursemember = CourseBase.get_course_member(request.user, cid)

        instructors = CourseMember.objects.filter(course = course, role= 'instructor')

        if not instructors.filter(hand_up= True).exists():
            render_dict['disbale_green'] = True
        else:
            render_dict['disbale_green'] = False
            if coursemember.hand_up == False:
                render_dict['status_green'] = 'Your hand is down in the Green list.'
            else:
                render_dict['status_green'] = 'Your hand is up in the Green list. '

        instructors = CourseMember.objects.filter(course = course, role= 'instructor')
        if not instructors.filter(hand_up_list_2= True).exists():
            render_dict['disbale_blue'] = True
        else:
            render_dict['disbale_blue'] = False
            if coursemember.hand_up_list_2 == False:
                render_dict['status_blue'] = 'Your hand is down in the Blue list.'
            else:
                render_dict['status_blue'] = 'Your hand is up in the Blue list. '

        instructors = CourseMember.objects.filter(course = course, role= 'instructor')
        if not instructors.filter(hand_up_list_3= True).exists():
            render_dict['disbale_red'] = True
        else:
            render_dict['disbale_red'] = False
            if coursemember.hand_up_list_3 == False:
                render_dict['status_red'] = 'Your hand is down in the Red list.'
            else:
                render_dict['status_blue'] = 'Your hand is up in the Red list. '

        instructors = CourseMember.objects.filter(course = course, role= 'instructor')
        if not instructors.filter(hand_up_list_4= True).exists():
            render_dict['disbale_yellow'] = True
        else:
            render_dict['disbale_yellow'] = False
            if coursemember.hand_up_list_4 == False:
                render_dict['status_yellow'] = 'Your hand is down in the Yellow list.'
            else:
                render_dict['status_yellow'] = 'Your hand is up in the Yellow list. '


        # if coursemember.hand_up_list_2 == False:
        #     render_dict['status_blue'] = 'Your hand is down in the Blue list.'
        # if coursemember.hand_up_list_3 == False:
        #     render_dict['status_red'] = 'Your hand is down in the Red list.'
        # if coursemember.hand_up_list_4 == False:
        #     render_dict['status_yellow'] = 'Your hand is down in the Yellow list.'

        # if coursemember.hand_up == True:
        #     render_dict['status_green'] = 'Your hand is up in the Green list. '
        # if coursemember.hand_up_list_2 == True:
        #     render_dict['status_blue'] = 'Your hand is up in the Blue list. '
        # if coursemember.hand_up_list_3 == True:
        #     render_dict['status_red'] = 'Your hand is up in the Red list. '
        # if coursemember.hand_up_list_4 == True:
        #     render_dict['status_yellow'] = 'Your hand is up in the Yellow list. '

        time_of_request = timezone.now()

        participations_total = CourseParticipation.objects.filter(
            participant = coursemember,
            count_in_calculations = True
        )
        participations_today = participations_total.filter(
            time_participated__startswith = time_of_request.date(), 
            real_participation= True
        )
        participations_bonus = participations_total.filter(
            time_participated__startswith = time_of_request.date(),
            real_participation = False 
        )

        total_points = 0 
        total_points_today = 0 
        total_points_bonus = 0
        for participation in participations_total:
            total_points += participation.participation_points_gained

        for participation in participations_today:
            total_points_today += participation.participation_points_gained

        for participation in participations_bonus:
            total_points_bonus += participation.participation_points_gained
        
        # render_dict["total_points"]= total_points
        render_dict["total_points_today"]= total_points_today
        render_dict["total_bonus_points"]= total_points_bonus




        return JsonResponse(render_dict)



    @staticmethod
    @login_required
    @chosen_course_required
    def count_hands_up(request):
        # CoursePermissions.require_instructor(request.user, cid)
        time_of_request = timezone.now()
        render_dict = dict()
        cid = request.session["course_id"]
        course = Course._default_manager.get(id=cid)
        list_of_spoken= []
        list_of_unspoken=[]
        blue_list_of_spoken= []
        blue_list_of_unspoken=[]
        red_list_of_spoken= []
        red_list_of_unspoken=[]
        yellow_list_of_spoken= []
        yellow_list_of_unspoken=[]

        spoken_students = []
        blue_spoken_students = []
        red_spoken_students = []
        yellow_spoken_students = []

        coursemember = CourseBase.get_course_member(request.user, course.id)


        if coursemember.hand_up == True:
            render_dict['green_enabled'] = True
        else:
            render_dict['green_enabled'] = False
        
        if coursemember.hand_up_list_2 == True:
            render_dict['blue_enabled'] = True
        else:
            render_dict['blue_enabled'] = False
        if coursemember.hand_up_list_3 == True:   
            render_dict['red_enabled'] = True
        else:
            render_dict['red_enabled'] = False
        if coursemember.hand_up_list_4 == True: 
            render_dict['yellow_enabled'] = True
        else:
            render_dict['yellow_enabled'] = False
            
        if not coursemember.hand_up == True and  not coursemember.hand_up_list_2 == True  and  not coursemember.hand_up_list_3 == True and  not coursemember.hand_up_list_4 == True:
            render_dict['count'] = 'Feature disabled.'
            render_dict['count_spoken'] = 'Feature disabled.'
            render_dict['count_total'] = [0,0,0,0]
            render_dict['count_total_spoken'] = [0,0,0,0]
        else:
            all_students = CourseMember.objects.filter(course = course, role='student', active= True)
            students = all_students.filter(hand_up= True)

            spoken_participations = CourseParticipation.objects.filter(
                participant__course = course,
                time_participated__startswith = time_of_request.date(),
                spoke_upon_participation = True,
                count_in_calculations = True
            ).order_by('-time_participated')
            
            all_spoken_students = spoken_participations.filter(participation_list = 1)
            green_already_spoken_count = len(all_spoken_students.order_by().values_list('participant',flat= True).distinct())
            spoken_students = list(all_spoken_students.filter(participant__hand_up = True).order_by().values_list('participant',flat= True).distinct())
            list_of_unspoken = [[x.user.first_name,x.user.last_name,x.id] for x in list(students) if x.id not in spoken_students]
            unspoken_count= len(list_of_unspoken)
            spoken_count = len(spoken_students)
            
            blue_students = all_students.filter(hand_up_list_2= True)
            all_blue_spoken_students = spoken_participations.filter(participation_list = 2)
            blue_already_spoken_count = len(all_blue_spoken_students.order_by().values_list('participant',flat= True).distinct())
            blue_spoken_students = list(all_blue_spoken_students.filter(participant__hand_up_list_2 = True).order_by().values_list('participant',flat= True).distinct())
            blue_list_of_unspoken = [[x.user.first_name,x.user.last_name,x.id] for x in list(blue_students) if x.id not in blue_spoken_students]

            blue_unspoken_count= len(blue_list_of_unspoken)
            blue_spoken_count = len(blue_spoken_students)

            red_students = all_students.filter(hand_up_list_3= True)
            all_red_spoken_students = spoken_participations.filter(participation_list = 3)
            red_already_spoken_count = len(all_red_spoken_students.order_by().values_list('participant',flat= True).distinct())
            red_spoken_students = list(spoken_participations.filter(participant__hand_up_list_3 = True).order_by().values_list('participant',flat= True).distinct())
            red_list_of_unspoken = [[x.user.first_name,x.user.last_name,x.id] for x in list(red_students) if x.id not in red_spoken_students]

            red_unspoken_count= len(red_list_of_unspoken)
            red_spoken_count = len(red_spoken_students)


            yellow_students = all_students.filter(hand_up_list_4= True)
            all_yellow_spoken_students = spoken_participations.filter(participation_list = 4)
            yellow_already_spoken_count = len(all_yellow_spoken_students.order_by().values_list('participant',flat= True).distinct())
            yellow_spoken_students = list(spoken_participations.filter(participant__hand_up_list_4 = True).order_by().values_list('participant',flat= True).distinct())
            yellow_list_of_unspoken = [[x.user.first_name,x.user.last_name,x.id] for x in list(yellow_students) if x.id not in yellow_spoken_students]

            yellow_unspoken_count= len(yellow_list_of_unspoken)
            yellow_spoken_count = len(yellow_spoken_students)




            render_dict['count'] = 'Unspoken: '+'Green: '+ str(unspoken_count) + ', Blue: ' + str(blue_unspoken_count) + ', Red: ' + str(red_unspoken_count) + ', Yellow: ' + str(yellow_unspoken_count) + '</br>' + 'Spoken:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;' + 'Green: '+ str(spoken_count) + ', Blue: ' + str(blue_spoken_count) + ', Red: ' + str(red_spoken_count) + ', Yellow: ' + str(yellow_spoken_count)
            render_dict['count_spoken'] =  'Green: '+ str(green_already_spoken_count) + ', Blue: ' + str(blue_already_spoken_count) + ', Red: ' + str(red_already_spoken_count) + ', Yellow: ' + str(yellow_already_spoken_count) + '</br>' + '&nbsp;'           
            render_dict['count_total'] = [
                unspoken_count+spoken_count,
                blue_unspoken_count+blue_spoken_count,
                red_unspoken_count+red_spoken_count,
                yellow_unspoken_count+yellow_spoken_count
                ]
            render_dict['count_total_spoken'] = [
                green_already_spoken_count,
                blue_already_spoken_count,
                red_already_spoken_count,
                yellow_already_spoken_count
                ]

            for std_id in spoken_students:
                std = CourseMember.objects.get(id= std_id)
                list_of_spoken.append([std.user.first_name,std.user.last_name,std.id])
            # print(list_of_spoken)
            for std_id in blue_spoken_students:
                std = CourseMember.objects.get(id= std_id)
                blue_list_of_spoken.append([std.user.first_name,std.user.last_name,std.id])
            # print(blue_list_of_spoken)

            for std_id in red_spoken_students:
                std = CourseMember.objects.get(id= std_id)
                red_list_of_spoken.append([std.user.first_name,std.user.last_name,std.id])

            for std_id in yellow_spoken_students:
                std = CourseMember.objects.get(id= std_id)
                yellow_list_of_spoken.append([std.user.first_name,std.user.last_name,std.id])


        render_dict['list_of_unspoken'] = list_of_unspoken
        render_dict['blue_list_of_unspoken'] = blue_list_of_unspoken
        render_dict['red_list_of_unspoken'] = red_list_of_unspoken
        render_dict['yellow_list_of_unspoken'] = yellow_list_of_unspoken
        
        render_dict['list_of_spoken'] = list_of_spoken
        render_dict['blue_list_of_spoken'] = blue_list_of_spoken
        render_dict['red_list_of_spoken'] = red_list_of_spoken
        render_dict['yellow_list_of_spoken'] = yellow_list_of_spoken

        return JsonResponse(render_dict)


    @staticmethod
    @login_required
    @chosen_course_required
    def count_already_spoken(request):

        time_of_request = timezone.now()
        render_dict = dict()
        cid = request.session["course_id"]
        course = Course._default_manager.get(id=cid)

        list_of_already_spoken= []

        coursemember = CourseBase.get_course_member(request.user, course.id)
        if not coursemember.hand_up == True and  not coursemember.hand_up_list_2 == True  and  not coursemember.hand_up_list_3 == True and  not coursemember.hand_up_list_4 == True:   
            render_dict['count_spoken'] = 'Feature disabled.'
        else:
            spoken_participations = CourseParticipation.objects.filter(
                participant__course = course,
                time_participated__startswith = time_of_request.date(),
                spoke_upon_participation = True,
                count_in_calculations = True
            ).order_by('-time_participated')

            already_spoken = []
            already_spoken_names = []
            
            green_already_spoken = []
            blue_already_spoken = []
            red_already_spoken = []
            yellow_already_spoken = []

            for participation in spoken_participations:
                if [participation.participant, participation.participation_list]  not in already_spoken_names:
                    already_spoken_names.append([participation.participant, participation.participation_list])
                    already_spoken.append([participation.participant, 'Green' if participation.participation_list == 1 else 'Blue' if participation.participation_list == 2 else 'Red' if participation.participation_list == 3 else 'Yellow'])

                # if (participation.participation_list==1) and (participation.participant not in green_already_spoken):
                #     green_already_spoken.append(participation.participant)

                # if (participation.participation_list==2) and (participation.participant not in blue_already_spoken):
                #     blue_already_spoken.append(participation.participant)

                # if (participation.participation_list==3) and (participation.participant not in red_already_spoken):
                #     red_already_spoken.append(participation.participant)

            # green_already_spoken_count = len(green_already_spoken)
            # blue_already_spoken_count = len(blue_already_spoken)
            # red_already_spoken_count = len(red_already_spoken)

            # render_dict['count_spoken'] =  'Count: '+'Green: '+ str(green_already_spoken_count) + ', Blue: ' + str(blue_already_spoken_count) + ', Red: ' + str(red_already_spoken_count) + '</br>' + '&nbsp;'

            for std in already_spoken:
                list_of_already_spoken.append([ std[0].user.first_name,std[0].user.last_name, std[1], '-' ])

        render_dict['list_of_already_spoken'] = list_of_already_spoken
        return JsonResponse(render_dict)


    @staticmethod
    @login_required
    @chosen_course_required
    def undo(request):
        render_dict = dict()
        cid = request.session["course_id"]
        CoursePermissions.require_course_member(request.user, cid)
        course = Course._default_manager.get(id=cid)
        coursemember = CourseBase.get_course_member(request.user, course.id)
        # CoursePermissions.require_instructor(request.user, cid)
        if coursemember.role == 'instructor':
            time_of_request = timezone.now()
            participations = CourseParticipation.objects.filter(
                participant__course = course,
                time_participated__startswith = time_of_request.date(),
                count_in_calculations = True
            ).order_by('-time_participated')
            if participations.exists():
                time_of_interest = participations[0].time_participated
                participations_to_remove = CourseParticipation.objects.filter(
                participant__course = course,
                time_participated = time_of_interest,
                count_in_calculations = True
                )
                # speaker_participation = participations_to_remove.filter(spoke_upon_participation= True)
                # if speaker_participation.exists():
                #     lid = speaker_participation[0].participation_list
                #     speaker = speaker_participation[0].participant
                #     if lid ==1:
                #         speaker.hand_up = True
                #     if lid ==2:
                #         speaker.hand_up_list_2 = True
                #     if lid ==3:
                #         speaker.hand_up_list_3 = True
                #     speaker.save()
                
                for participation_to_remove in participations_to_remove:
                    participation_to_remove.count_in_calculations = False
                    participation_to_remove.save()


        time_of_request = timezone.now()
        render_dict = dict()
        cid = request.session["course_id"]
        course = Course._default_manager.get(id=cid)

        list_of_already_spoken= []

        coursemember = CourseBase.get_course_member(request.user, course.id)
        if not coursemember.hand_up == True and  not coursemember.hand_up_list_2 == True  and  not coursemember.hand_up_list_3 == True and  not coursemember.hand_up_list_4 == True:   
            render_dict['count_spoken'] = 'Feature disabled.'
        else:
            spoken_participations = CourseParticipation.objects.filter(
                participant__course = course,
                time_participated__startswith = time_of_request.date(),
                spoke_upon_participation = True,
                count_in_calculations = True
            ).order_by('-time_participated')

            already_spoken = []
            already_spoken_names = []
            green_already_spoken = []
            blue_already_spoken = []
            red_already_spoken = []
            yellow_already_spoken = []

            for participation in spoken_participations:
                if participation.participant not in already_spoken_names:
                    already_spoken_names.append(participation.participant)
                    already_spoken.append([participation.participant, 'Green' if participation.participation_list == 1 else 'Blue' if participation.participation_list == 2 else 'Red' if participation.participation_list == 3 else 'Yellow'])

                if (participation.participation_list==1) and (participation.participant not in green_already_spoken):
                    green_already_spoken.append(participation.participant)

                if (participation.participation_list==2) and (participation.participant not in blue_already_spoken):
                    blue_already_spoken.append(participation.participant)

                if (participation.participation_list==3) and (participation.participant not in red_already_spoken):
                    red_already_spoken.append(participation.participant)

                if (participation.participation_list==4) and (participation.participant not in yellow_already_spoken):
                    yellow_already_spoken.append(participation.participant)

            green_already_spoken_count = len(green_already_spoken)
            blue_already_spoken_count = len(blue_already_spoken)
            red_already_spoken_count = len(red_already_spoken)
            yellow_already_spoken_count = len(yellow_already_spoken)

            render_dict['count_spoken'] =  'Count: '+'Green: '+ str(green_already_spoken_count) + ', Blue: ' + str(blue_already_spoken_count) + ', Red: ' + str(red_already_spoken_count) + ', Yellow: ' + str(yellow_already_spoken_count) + '</br>' + '&nbsp;'

            for std in already_spoken:
                list_of_already_spoken.append([ std[0].user.first_name,std[0].user.last_name, std[1], '-' ])

        render_dict['list_of_already_spoken'] = list_of_already_spoken
        return JsonResponse(render_dict)


    @staticmethod
    @login_required
    @chosen_course_required
    def disqualify_all(request):
        cid = request.session["course_id"]
        CoursePermissions.require_instructor(request.user, cid)

        course = Course._default_manager.get(id=cid)
        students = CourseMember.objects.filter(course = course, 
            role='student', active= True)
        for student in students:
            student.qualified = False
            student.save()
        #message.sucess('Every student was disqualified.')
        return HttpResponse('Every student was disqualified.')


    @staticmethod
    @login_required
    @chosen_course_required
    def reset_class_participation(request):
        cid = request.session["course_id"]
        CoursePermissions.require_instructor(request.user, cid)
        course = Course._default_manager.get(id=cid)
        students = CourseMember.objects.filter(course = course, 
            role='student', active= True)
        for student in students:
            student.spoken = False
            student.first_hand_up= True
            student.save()
        return HttpResponse('Every student was cleared for class participation.')

    @staticmethod
    @login_required
    @chosen_course_required
    def reset_participation_points(request):
        cid = request.session["course_id"]
        CoursePermissions.require_instructor(request.user, cid)

        course = Course._default_manager.get(id=cid)
        students = CourseMember.objects.filter(course = course, 
            role='student', active= True)
        for student in students:
            student.participation_points = 0
            student.save()
        return HttpResponse('Every student was cleared for weekly participation points.')

    @staticmethod
    def update_course(request):
        render_dict = dict()
        if request.method == "POST":
            cid = request.POST.get("course")
            request.session["cid"] = cid
            url_next = request.GET.get("next", "/")
            return HttpResponseRedirect(url_next)

        return djangoRender(request, "dashboard.html", render_dict)

    @staticmethod
    def start_timer(request):
        render_dict = dict()
        cid = request.session["course_id"]
        CoursePermissions.require_course_staff(request.user, cid)
        course = Course._default_manager.get(id=cid)
        ta = CourseBase.get_course_member(request.user, course.id)
        participations = CourseParticipation.objects.filter(participant = ta).order_by('-id')
        # print (participations)
        if participations.exists():
            if participations[0].participation_list == 11:  
                CourseParticipation.objects.create(
                    participant  = ta, 
                    time_participated = timezone.now(),
                    spoke_upon_participation = False,
                    participation_list= 10,
                    real_participation = True,
                    count_in_calculations = True
                )
                render_dict['response'] = 'Your timer has started!'
            else:  
                render_dict['response'] = 'You have a running timer already!'
                return JsonResponse(render_dict)   
        else: 
            CourseParticipation.objects.create(
                participant  = ta, 
                time_participated = timezone.now(),
                spoke_upon_participation = False,
                participation_list= 10,
                real_participation = True,
                count_in_calculations = True
            )
            render_dict['response'] = 'Your timer has started!'
        return JsonResponse(render_dict) 


    @staticmethod
    def stop_timer(request):
        render_dict = dict()
        cid = request.session["course_id"]
        CoursePermissions.require_course_staff(request.user, cid)
        course = Course._default_manager.get(id=cid)
        ta = CourseBase.get_course_member(request.user, course.id)
        participations = CourseParticipation.objects.filter(participant = ta).order_by('-id')
        if participations.exists():
            if participations[0].participation_list == 10:  
                CourseParticipation.objects.create(
                    participant  = ta, 
                    time_participated = timezone.now(),
                    spoke_upon_participation = False,
                    participation_list= 11,
                    real_participation = True,
                    count_in_calculations = True
                )
                render_dict['response'] = 'Your timer has stopped!'
            else:
                render_dict['response'] = 'You do not have an active timer!'
        else:
            render_dict['response'] = 'You do not have an active timer!'
        return JsonResponse(render_dict) 





def call_if_callable(item):
    if callable(item):
        return item()
    return item

