from django_cron import CronJobBase, Schedule
from .models import Assignment
from django.utils import timezone
import subprocess
from django.shortcuts import get_object_or_404, HttpResponseRedirect, HttpResponse
from peer_grade.dependability_calculation import export_to_csv_assignment_grades, import_ci_from_file
from walrus import *
import redis
from peer_course.models import Course, CourseMember, CourseParticipation
from peer_assignment.models import SubmissionComponent, AssignmentSubmission
from peer_review.models import ReviewAssignment, ReviewContent
from peer_evaluation.models import EvaluationAssignment, EvaluationContent
from datetime import datetime, timedelta

class ReleaseAssignment(CronJobBase):
    RUN_EVERY_MINS = 10  # every 1 hour

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = "peer_assignment.release_assignment"  # a unique code

    def do(self):
        Assignment._default_manager.filter(release_time__lte=timezone.now()).update(
            browsable=True
        )


class StopTAtimer(CronJobBase):
    RUN_EVERY_MINS = 10  # every 1 hour

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = "peer_assignment.stoptatimer"  # a unique code

    def do(self):
        tas = CourseMember.objects.filter(course_id =25, role = 'ta')
        time_now = timezone.now()
        for ta in tas:
            rvs = ReviewAssignment.objects.filter(grader = ta).order_by('-modification_date')
            evals = EvaluationAssignment.objects.filter(grader = ta).order_by('-modification_date')
            if rvs.exists():
                time_diff = time_now - rvs[0].modification_date 
                stoppage_time = rvs[0].modification_date
            if evals.exists():
                if time_now - evals[0].modification_date < time_diff:
                    time_diff = time_now - evals[0].modification_date 
                    stoppage_time = evals[0].modification_date 
            if time_diff > timedelta(seconds = 3000) :   
                participations = CourseParticipation.objects.filter(participant = ta).order_by('-id')
                if participations.exists():
                    if participations[0].participation_list == 10 and time_now  - participations[0].time_participated  > timedelta(seconds = 3000):  
                        CourseParticipation.objects.create(
                            participant  = ta, 
                            time_participated = stoppage_time,
                            spoke_upon_participation = False,
                            participation_list= 11,
                            real_participation = False,
                            count_in_calculations = True
                        )