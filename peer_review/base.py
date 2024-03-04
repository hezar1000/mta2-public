import math, random, re
import csv, io
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
import statistics

from itertools import chain

from peer_course.models import Course, CourseMember
from peer_assignment.models import Assignment, AssignmentSubmission
from peer_assignment.base import AssignmentBase
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden


from peer_evaluation.base import EvaluationBase

from .choices import *
from .models import *


class ReviewBase:
    SPOT_CHECK_HOOKS = []

    @staticmethod
    def add_spot_check_hook(func):
        ReviewBase.SPOT_CHECK_HOOKS.append(func)

    @staticmethod
    def get_tas_for_assignment(aid):
        assignment = Assignment._default_manager.get(pk=aid)
        return CourseBase.get_tas(assignment.course.id)

    @staticmethod
    def get_students_for_assignment(aid):
        assignment = Assignment._default_manager.get(pk=aid)
        course = assignment.course
        return course.members.filter(role='student', active= True, qualified= True)

    @staticmethod
    def get_independent_students_for_assignment(aid):
        assignment = Assignment._default_manager.get(pk=aid)
        course = assignment.course
        return course.members.filter(role="student", is_independent=True, qualified=True)

    @staticmethod
    def get_supervised_students_for_assignment(aid):
        assignment = Assignment._default_manager.get(pk=aid)
        course = assignment.course
        return course.members.filter(role="student", is_independent=False, qualified= True)

    @staticmethod
    def get_random_review(assignment):
        size = ReviewAssignment._default_manager.filter(
            submission__assignment=assignment
        ).count()
        rrid = int(random.random() * size)
        return ReviewAssignment._default_manager.filter(
            submission__assignment=assignment
        )[rrid]

    # Why do we need this?
    @staticmethod
    def assign_self_reviews(aid, rid):

        rubric = Rubric._default_manager.get(pk=rid)
        submissions = AssignmentSubmission._default_manager.filter(assignment__id=aid)

        for submission in submissions:
            author = submission.author
            if ReviewAssignment._default_manager.filter(
                submission=submission, grader=author
            ).exists():
                continue
            else:
                ReviewAssignment._default_manager.create(
                    submission=submission, grader=author
                )

    @staticmethod
    def get_submission_without_ta_review(aid):
        return (
            AssignmentSubmission._default_manager.filter(
                assignment__id=aid, calibration_id=0
            )
            .exclude(reviewassignment__grader__role="ta")
            .exclude(reviewassignment__grader__role="instructor")
        )

    @staticmethod
    def submission_without_ta_review_count(aid):
        return ReviewBase.get_submission_without_ta_review(aid).count()

    @staticmethod
    def upload_spot_checks(csv_file):
        count=0
        decoded_file = csv_file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        for row in csv.reader(io_string, delimiter=',', quotechar='|'):
            sub= AssignmentSubmission._default_manager.filter(id=int(row[0]))
            ta= CourseMember._default_manager.filter(user__username=row[1])
            if sub.exists() and ta.exists():
               review = ReviewAssignment._default_manager.create(submission=sub[0], grader=ta[0])
            count=count+1
            #By default, assigns evaluation per review
            EvaluationBase._assign_evaluation_on_spot_check(sub[0], review)
        return count

    @staticmethod
    def upload_spot_checking_priorities(csv_file):
        count=0
        decoded_file = csv_file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        for row in csv.reader(io_string, delimiter=',', quotechar='|'):
            subs= AssignmentSubmission._default_manager.filter(id=int(row[0]))
            if subs.exists():
                sub= subs[0]
                sub.spotchecking_priority = float(row[1])
                sub.save()
                count=count+1
        return count


    @staticmethod
    def assign_spot_checks(
        aid, num_reviews, tas, per_question_review=False, evaluate_student_reviews=False
    ):
        """
            Randomly assigns reviews to `num_reviews` submissions that didn't already
            have TA reviews assigned to them.
            Will cyclically assign TAs until the required number of submissions is met.

            Pre-conditions:
              - param `tas` is not empty
        """

        assignment = Assignment._default_manager.get(pk=aid)

        all_subs = ReviewBase.get_submission_without_ta_review(aid)
        supervised_subs = all_subs.filter(author__is_independent=False)

        # order submissions randomly
        independent_subs = list(
            all_subs.filter(author__is_independent=True).order_by("?")
        )

        if num_reviews != 0:
            for sub in independent_subs:
                reviews = sub.reviewassignment_set.filter(submitted=True)
                if reviews.exclude(grader__role="student").exists() or not reviews.exclude(grader__role="ta").exists():
                    sub.rev_variance = -1
                    sub.median = -1
                else: 
                    sub.rev_variance = statistics.pvariance(
                        [r.assigned_grade for r in reviews]
                    )

                    sub.median = statistics.median(
                        [r.assigned_grade for r in reviews]
                    )

            sorted_subs = sorted(
                independent_subs, key=lambda x: x.rev_variance, reverse=True
            )

            independent_sorted_subs = sorted_subs[:int(num_reviews/2)]

            sorted_subs1 = sorted(
                sorted_subs[(int(num_reviews/2))+1:], key=lambda x: x.median, reverse=True
            )

            independent_sorted_subs1 = sorted_subs1[:int(num_reviews/2)]

        else:
            independent_sorted_subs = []
            independent_sorted_subs1 = []

        # order tas randomly
        if not per_question_review:
            tas = list(tas.order_by("?"))
            num_tas = len(tas)
        else:
            tas_list = [list(t.order_by("?")) for t in tas]
            num_tas = [len(t) for t in tas_list]

        #for i, sub in enumerate(all_subs):
        for i, sub in enumerate(chain(supervised_subs, independent_sorted_subs, independent_sorted_subs1)):
            if not per_question_review:
                review = ReviewAssignment._default_manager.create(
                    submission=sub, grader=tas[i % num_tas]
                )
                if evaluate_student_reviews:
                    EvaluationBase._assign_evaluation_on_spot_check(sub, review)
            else:
                for j, q in enumerate(assignment.questions.all()):
                    review = ReviewAssignment._default_manager.create(
                        submission=sub, grader=tas_list[j][i % num_tas[j]], question=q
                    )
                    ## Evaluation should not be needed in this case
                    ## but the logic is handled in the forms
                    if evaluate_student_reviews:
                        EvaluationBase._assign_evaluation_on_spot_check(sub, review)

            # for f in ReviewBase.SPOT_CHECK_HOOKS:
            #     if callable(f):
            #         f(sub, review)

        return supervised_subs.count() + len(independent_sorted_subs) + len(independent_sorted_subs1)
        #return all_subs.count()

    @staticmethod
    def assign_calibration_reviews(aid, num_calibration_reviews):
        calibration_submissions = (
            AssignmentSubmission._default_manager.filter(assignment_id=aid)
            .exclude(calibration_id=0)
            .all()
        )
        supervised_students = ReviewBase.get_supervised_students_for_assignment(aid)

        for i in supervised_students:
            already_assgned_cals = (
                ReviewAssignment._default_manager.filter(submission__id=aid, grader=i)
                .exclude(submission__calibration_id=0)
                .count()
            )
            num_cal = num_calibration_reviews - already_assgned_cals
            sampled_calibrations = random.sample(
                list(calibration_submissions), num_calibration_reviews
            )
            for j in range(num_cal):
                if ReviewAssignment._default_manager.filter(
                    submission=sampled_calibrations[j], grader=i
                ).exists():
                    pass
                else:
                    ReviewAssignment._default_manager.create(
                        submission=sampled_calibrations[j], grader=i
                    )

    @staticmethod
    def __assign_student_reviews(num_reviews, submissions):
        num_submissions = submissions.count()
        if num_submissions==0:
            return HttpResponseForbidden("There are no more submissions")

        #submissions = AssignmentSubmission.objects.filter(assignment__id=aid).order_by('?').all()
        
        print('num of submissions is %s' % num_submissions)
        aid= submissions[0].assignment.id
        #students = get_students_for_assignment(aid)
        students = CourseMember.objects.filter(course= submissions[0].assignment.course, role='student', active= True, qualified= True)
        for i in range(len(submissions)):
            submission = submissions[i]
            num_student_reviews_assigned = ReviewAssignment.objects.filter(
                submission=submission, grader__in=students).count()
            index = (i + 1) % num_submissions
            while (num_student_reviews_assigned < num_reviews) :
                reviewer = submissions[index].author
                if ReviewAssignment.objects.filter(
                    submission=submission, 
                    grader=reviewer).exists():
                    index = (index + 1) % num_submissions
                    continue
                else:
                    print('%s, %s' % (submission, reviewer))
                    ReviewAssignment.objects.create(
                        submission=submission, 
                        grader=reviewer)
                    num_student_reviews_assigned += 1
                    index = (index + 1) % num_submissions

#        for student in students:
#            count= ReviewAssignment.objects.filter(grader= student, submission__assignment_id=aid).count()
#            if count < num_reviews:
#                submissions_random= submissions.order_by('?')
#                subs_to_assign = submissions_random[:(num_reviews-count)]
#                for sub in subs_to_assign:
#                    ReviewAssignment.objects.create(submission=sub, grader=student)
                
            # index=0
            # while ReviewAssignment.objects.filter(grader= student, submission__assignment_id=aid).count() < num_reviews:
            #     submissions_random= submissions.order_by('?')
            #     submission = submissions_random[index]
            #     if ReviewAssignment.objects.filter(
            #         submission=submission, 
            #         grader=student).exists():
            #         index = (index + 1) % num_submissions
            #         continue
            #     else:
            #         print('%s, %s' % (submission, student))
            #         ReviewAssignment.objects.create(
            #             submission=submission, 
            #             grader=student)
            #         index = (index + 1) % num_submissions




#        subs_count = subs.count()

#        if subs_count ==0:
#            return HttpResponseForbidden("There are no more submissions")

    #    students = subs.values_list("author", flat=True).distinct()
    #   students = CourseMember.objects.filter(role = 'student', qualified=True, course=subs[0].author.course, active=True).order_by("?")

    #    for i, sub in enumerate(subs):

    #        num_already_assigned = ReviewAssignment._default_manager.filter(
    #            submission=sub, grader__in=students
    #        ).count()

    #        index = (i + 1) % subs_count

    #       while num_already_assigned < num:

 #               reviewer = subs[index].author
  #              if ReviewAssignment._default_manager.filter(
   #                 submission=sub, grader=reviewer
    #            ).exists():
     #               index = (index + 1) % subs_count
      #          else:
       #             ReviewAssignment._default_manager.create(
        #                submission=sub, grader=reviewer
         #           )

#                    num_already_assigned += 1
 #                   index = (index + 1) % subs_count

#        students=CourseMember._default_manager.filter(
#                role = 'student', qualified=True, course=subs[0].author.course, active=True, is_independent = subs[0].author.is_independent
#            )    
#        students_count= students.count()
#        subss= subs.order_by("?")
#        if (4*students_count)/3 > subs_count:
#            for student in students:        
#                for sub in subss:
#                    if ReviewAssignment._default_manager.filter(
#                        grader=student, submission__calibration_id=0, submission__assignment_id=subs[0].assignment_id
#                    ).count() > num :
#                        break
#                    if  ReviewAssignment._default_manager.filter(
#                    submission=sub, grader__in=students
#                    ).count() > num:
#                        continue

#                    if ReviewAssignment._default_manager.filter(
#                            submission=sub, grader=student
#                    ).exists() or student == sub.author:
#                        continue
#                    else: 
#                        ReviewAssignment._default_manager.create(
#                            submission=sub, grader=student
#                    )
                
                
            # for sub in subs:
            #     reviewers= students.exclude(user=sub.author.user).order_by("?")
                
            #     reviewer_count= reviewers.count()

            #     num_already_assigned = ReviewAssignment._default_manager.filter(
            #         submission=sub, grader__in=reviewers
            #     ).count()
                
            #     i=0

            #     while num_already_assigned < num:
                    
            #         reviewer = reviewers[i]
            #         if ReviewAssignment._default_manager.filter(
            #             submission=sub, grader=reviewer
            #         ).exists() or ReviewAssignment._default_manager.filter(
            #             grader=reviewer, submission__calibration_id=0, submission__assignment_id=sub.assignment_id
            #         ).count() > num :
            #             i = (i + 1) % reviewer_count
            #         else:
            #             ReviewAssignment._default_manager.create(
            #                 submission=sub, grader=reviewer
            #             )

            #             num_already_assigned += 1
            #             i = (i + 1) % reviewer_count      


        # for student in students:
        #     num_reviews= ReviewAssignment._default_manager.filter(
        #         grader=student, submission__calibration_id=0, submission__assignment_id=subs[0].assignment_id
        #     ).count()


            # while num_reviews < num+1: 
            #     subs_for_stu= AssignmentSubmission._default_manager.filter(
            #         assignment__id=subs[0].assignment_id, calibration_id=0, author__is_independent= student.is_independent
            #     ).exclude(author=student).order_by("?")

            #     #sampled_subs= random.sample(
            #     #list(subs_for_stu), num-num_reviews+1 )

            #     if subs_for_stu.exists():
            #         for i in range(num-num_reviews):
            #             if ReviewAssignment._default_manager.filter(
            #                 submission=subs_for_stu[i], grader__in=students
            #             ).count() < num +1 and not ReviewAssignment._default_manager.filter(
            #                 submission=subs_for_stu[i] , grader=student
            #             ).exists() :
            #                 ReviewAssignment._default_manager.create(
            #                     submission=subs_for_stu[i], grader=student
            #                 )
            #     else: 
            #         break





    @staticmethod
    def assign_student_reviews(
        aid, num=None, num_supervised=None, num_independent=None
    ):
        """
        Assigns student reviews for existing assignment submissions

        Can be called in two ways:
          - if `num` is passed: assigns reviews normally (happens if `course.enable_independent_pool == True`)
          - o.w. both `num_supervised` and `num_independent` should be supplied
            * in this case assignment to independent/supervised pools are separate and use different # of assignments
        """

        # order submissions randomly
        subs = AssignmentSubmission._default_manager.filter(
            assignment__id=aid, calibration_id=0
        )

        if num is not None:
            ReviewBase.__assign_student_reviews(num, subs)
        else:
            ReviewBase.__assign_student_reviews(
                num_independent, subs.filter(author__is_independent=True).order_by("?")
            )
            ReviewBase.__assign_student_reviews(
                num_supervised, subs.filter(author__is_independent=False).order_by("?")
            )

    # TODO: check: why do we need this :(
    # def save_review_files(cleaned_data, revasgn, request) :
    #     has_file = False
    #     if revasgn == None :
    #         raise ValueError('ReviewAssignment cannot be None')

    #     for field_name, field_content in cleaned_data.items() :
    #         found = re.search('rq_file_([0-9]+)', field_name)
    #         if found is None :
    #             continue

    #         rq_id = found.group(1)
    #         print('rq_id', rq_id)
    #         print('field_name', field_name)

    #         rq = RubricQuestion._default_manager.get(pk=rq_id)
    #         rc = ReviewContent._default_manager.get(
    #             rubric_question=rq,
    #             review_assignment=revasgn,
    #         )

    #         files = request.FILES.getlist(field_name)
    #         for f in files:
    #             rcf = ReviewContentFile(
    #                 attachment=f,
    #                 review_content=rc,
    #             )
    #             rcf.save()
    #         rc.content = "files"
    #         rc.save()

    #         has_file = True
    #     return has_file

    @staticmethod
    def upload_student_reviews(csv_file):
        count=0
        decoded_file = csv_file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        for row in csv.reader(io_string, delimiter=',', quotechar='|'):
            sub= AssignmentSubmission._default_manager.filter(id=int(row[0]))
            if sub.exists():
                stu= CourseMember._default_manager.filter(user__username=row[1], course= sub[0].assignment.course)
            if sub.exists() and stu.exists():
                review = ReviewAssignment._default_manager.create(submission=sub[0], grader=stu[0])
                count=count+1
        return count



    @staticmethod
    def remove_review_files(revasgn):
        ReviewContentFile._default_manager.filter(
            review_content__review_assignment=revasgn
        ).delete()
        return True

    @staticmethod
    def find_available_submissions(user, aid):
        "Return a queryset of submissions that have not been reviewed by a TA"

        assignment = Assignment._default_manager.get(pk=aid)
        course = assignment.course

        tas = course.members.filter(role="ta")
        print("TAs: %s" % tas)

        submissions = assignment.assignmentsubmission_set.all()
        print("all submissions: %s" % submissions)

        submissions = submissions.exclude(reviewassignment__grader__in=tas)
        print("available submissions: %s" % submissions)

        return submissions

    def get_random_object(queryset):
        count = queryset.count()
        rand_index = random.randint(0, count - 1)
        return queryset.all()[rand_index]

    @staticmethod
    def get_user_review_by_status(user, course=None):
        if course is None:
            courses = CourseBase.get_courses(user)  # .order_by('displayname')
        else:
            courses = [course]

        return ReviewAssignment._default_manager.filter(
            submission__assignment__course__in=courses, grader__user=user
        )

    @staticmethod
    def get_my_reviews(user, course, option="all"):
        if option == "pending":
            return [
                ra
                for ra in ReviewAssignment._default_manager.filter(
                    submission__assignment__course=course, grader__user=user
                )
                if (
                    ra.submission.calibration_id != 0
                    or not ra.deadline_passed()
                    or ra.grader.role == "ta"
                    or ra.grader.role == "instructor"
                )
                and not ra.reviewcontent_set.exists()
            ]
        elif option == "all":
            return ReviewAssignment._default_manager.filter(
                submission__assignment__course=course, grader__user=user
            ).order_by("-deadline")

    @staticmethod
    def get_review_components_dict(review):
        components = {}

        for sc in review.submission.components.all():
            # TODO: refactor this part out
            content_queryset = ReviewContent._default_manager.filter(
                review_assignment=review, submission_component=sc
            )
            contents = list()

            for content_obj in content_queryset:
                content_dict = dict()

                content_dict["question"] = content_obj.choice.question.text
                content_dict["content_obj"] = content_obj
                content_dict["reason"] = content_obj.reason

                # if content_obj.choice.question.category == MULTIPLECHOICE :
                choice_id = int(content_obj.choice.id)
                chosen = RubricQuestionMultipleChoiceItem._default_manager.get(
                    pk=choice_id
                )
                content_dict["answer"] = chosen.text
                content_dict["grade"] = chosen.marks
                content_dict["max_grade"] = chosen.question.max_grade()

                # elif content_obj.choice.question.category == TEXT :
                #     content_dict['answer'] = content_obj.choice.id

                # elif content_obj.choice.question.category == FILE :
                #     pass
                # content_dict['answer'] = ReviewUtils.get_file_links(
                #     content_obj.choice.question, review)

                contents.append(content_dict)

            components[sc.id] = contents

        return components
