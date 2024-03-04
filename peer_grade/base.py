import statistics, random
from django.db.models import Q
from django.conf import settings
import csv, io


from peer_course.base import CourseBase
from peer_course.models import CourseMember

from peer_review.choices import MULTIPLECHOICE
from peer_evaluation.models import EvaluationContent
from peer_assignment.models import *
from peer_review.models import *


from .models import Appeal, InaptReport, GradingItem
from .choices import CLOSED, RESOLVED


class GradeHelper:
    @staticmethod
    def get_grading_by_priority(l):
        """
            Select the first item with 'grade' value not equal to `None`
            Returns {'method': None, 'grade': None} if such a grade is not found
        """
        return next(
            (item for item in l if item["grade"] is not None),
            {"method": None, "grade": None},
        )


class GradeBaseMain(object):
    def aggregate(self, grade_list):
        """
        Aggregate the grades from multiple reviews to get a single final grade
        We use the `median` function here
        """
        if grade_list:
            return statistics.median(grade_list)
        return None

    def compute_grade_by_reviews(self, reviews, rubric):
        """
        For now, this does nothing but call aggregate on the assigned grades and return the value
        for empty lists, the output is `None`
        """
        if not reviews or rubric is None:
            return None

        grades = [
            self.aggregate(
                [r.assigned_grade() for r in reviews.filter(choice__question=question)]
            )
            for question in rubric.questions.all()
        ]

        if None in grades:
            return None
        return sum(grades)

    def grading_priority(self):
        reviews = lambda sc: sc.reviewcontent_set.filter(
            review_assignment__submitted=True,
            review_assignment__flag=None,  # Flagged reviews do not count
        )
        return [
            {"method": "Manual", "grade": lambda sc: sc.manual_grade},
            # sc.ta_review_grade,
            # sc.automatic_grade,
            # TODO: this is not how it should be used normally; maybe change that one if necessary?
            # TODO: add caching
            {
                "method": "TA",
                "grade": lambda sc: self.compute_grade_by_reviews(
                    reviews(sc).filter(
                        Q(review_assignment__grader__role="ta")
                        | Q(review_assignment__grader__role="instructor")
                    ),
                    sc.question.rubric,
                ),
            },
            {
                "method": "Peer",
                "grade": lambda sc: self.compute_grade_by_reviews(
                    reviews(sc).filter(review_assignment__grader__role="student"),
                    sc.question.rubric,
                ),
            },
        ]

    def compute_submission_component_grading(self, sc):
        """
            Computes the grade for one question

            Priority of assigned grades:
              - Manual
              - TA
              - Aggregate Peer grade
        """
        if sc.question.category == MULTIPLECHOICE:
            choice = sc.question.choices.filter(pk=sc.content).first()
            if choice:
                return {"grade": choice.marks, "method": "Quiz"}
            return {"grade": None, "method": "Quiz"}
        for p in self.grading_priority():
            grade = p["grade"](sc)
            if grade is not None:
                return {"grade": grade, "method": p["method"]}
        return {"method": None, "grade": None}

    def compute_submission_component_grade(self, sc):
        return self.compute_submission_component_grading(sc)["grade"]

    def max_evaluation_grade(self, assignment):
        return sum(
            [q.evaluation_rubric.max_total_grade() for q in assignment.questions.all()]
        )

    def compute_review_evaluation(self, review):
        if True:
            """Computes the grade assigned to review by the TA evaluations"""
            grade = 0
            for sc in review.reviewcontent_set.values_list(
                "submission_component", flat=True
            ).distinct():
                ecs = EvaluationContent._default_manager.filter(
                    evaluation__review=review, submission_component_id=sc
                )
                if not ecs.exists():
                    return None
                grade += statistics.median([ec.assigned_grade() for ec in ecs])
            return grade   
        else:
            """Computes the grade assigned to review by the consensus grade rule"""
            final_grade= review.submission.final_grade
            review_grade= review.assigned_grade
            return (abs(final_grade-review_grade)/final_grade)*10

    def compute_grade_by_review(self, review):
        """
            ** Not part of the final grade  **

            Computes the grade assigned by a specific reviewer
            Usecase: in page `review:assignment_review_list`, shows the grade per reviewer
        """
        return sum([rc.assigned_grade() for rc in review.reviewcontent_set.all()])

    def import_student_grades(csv_file):
        count=0
        decoded_file = csv_file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        for row in csv.reader(io_string, delimiter=',', quotechar='|'):
            subs= AssignmentSubmission._default_manager.filter(id=int(row[0]))
            sub=subs[0]

            # Assignments graded by TAs: ignore final grade; change student weights to 0
            if sub.final_grading_method == 'TA':
                reviews = ReviewAssignment._default_manager.filter(submission=sub, grader__role='student')
                for review in reviews:
                    review.markingload = 0
                    review.save()

            # Assignments without TA grades: update final grade and weights
            else:
                sub.final_grade = float(row[1])
                sub.final_grading_method = "Peer"
                sub.save()
                for i in range(int((len(row)-2)/2)):
                    review = ReviewAssignment._default_manager.get(submission=sub, grader__user__username=row[2*(i+1)])
                    review.markingload = float(row[2*(i+1)+1])
                    review.save()

            count=count+1

        return count

    def upload_grading_items(csv_file, cid):  # format: gradee - week - grade type (peer review or participation?) - grade - max grade- grading_method (TA or what?) - comments
        count=0
        decoded_file = csv_file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        for row in csv.DictReader(io_string):
            gradee = CourseMember._default_manager.get(user__username=row['gradee'], course_id = cid)
            week = row['week']
            grade_type = row['grade type']  # peer review or participation ... 
            grade = row['grade']
            max_grade = row['max grade']
            grading_method = row['grading method'] #TA or peer or ?
            comments = row['comments']
            grading_items = GradingItem._default_manager.filter(gradee  = gradee, grade_type = grade_type, grading_period = week)
            if grading_items.exists():
                grading_item = grading_items[0]
                grading_item.grade = grade
                grading_item.max_grade = max_grade
                grading_item.grading_method = grading_method
                grading_item.comments = comments
                grading_item.save()
            else:
                GradingItem._default_manager.create(
                    gradee  = gradee,
                    grading_period = week,
                    grade_type = grade_type,
                    grade = grade,
                    max_grade = max_grade,
                    grading_method = grading_method,
                    comments = comments
                )
            count += 1
        return count




    def upload_component_grades(csv_file):
        # CSV format: [submission_id, sub_comp_id, rubric_choice_id]
        count=0
        decoded_file = csv_file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        for row in csv.reader(io_string, delimiter=',', quotechar='|'):
            sub= AssignmentSubmission._default_manager.get(id=int(row[0]))
            graders= CourseMember._default_manager.filter(course= sub.assignment.course, role = 'instructor')
            questions = AssignmentQuestion.objects.filter(assignment= sub.assignment)
            if ReviewAssignment._default_manager.filter(submission=sub, grader=graders[0], visible= False).exists():
                new_rvs= ReviewAssignment._default_manager.filter(submission=sub, grader=graders[0], visible= False)
                new_rv= new_rvs[0]
            else:    
                new_rv = ReviewAssignment._default_manager.create(
                    submission=sub,
                    grader=graders[0], 
                    visible= False, 
                    # assigned_grade= float(row[1]), 
                    submitted= True, 
                    markingload = 1,
                )
            #    new_rvs = ReviewAssignment._default_manager.filter(submission=sub, grader=graders[0])
           #  new_rv= new_rvs[0]
             #   new_rv.assigned_grade = float(row[1])
            

            sub_comp= SubmissionComponent._default_manager.get(id= int(row[1]) )
          #  rubric_question = RubricQuestion._default_manager.get(id = int(row[2]) )
        
#            rubric_question = rubric_questions[0]
#                rubric_item = RubricQuestionMultipleChoiceItem._default_manager.create(question = rubric_question, text= 'Inference output')
#            rubric_item=   RubricQuestionMultipleChoiceItem._default_manager.get(question = rubric_question)
#            rubric_item = rubric_items[0]
#            sub_comp= sub_comps[0]
            ReviewContent._default_manager.create(
                review_assignment= new_rv, submission_component= sub_comp,
                choice_id= int(row[2]), reason = "Component wise wighted average"
            )
            count=count+1
        return count

# TODO: use visitor pattern instead
class GradeBaseComponentWise(GradeBaseMain):
    def compute_submission_grade(self, submission):
        grades = [x.final_grade() for x in submission.components.all()]
        if None in grades:
            return None
        return sum(grades)

    def get_submission_grading_method(self, submission):
        gradings = [x.final_grading() for x in submission.components.all()]

        return " and ".join(
            sorted(
                set(
                    [x["method"] for x in gradings if x["method"] is not None]
                    or ["Not graded"]
                )
            )
        )


class GradeBaseReviewsFirst(GradeBaseMain):
    def compute_submission_grade(self, submission):
        if submission.components.filter(question__category=MULTIPLECHOICE).exists():
            grades = [x.final_grade() for x in submission.components.all()]
            if None in grades:
                return None
            return sum(grades)

        reviews = submission.reviewassignment_set.filter(
            submitted=True, flag=None  # Flagged reviews do not count
        )
        if reviews.exclude(grader__role="student").exists():
            if reviews.filter(is_groundtruth=True).exists():
                reviews = reviews.filter(is_groundtruth=True)
            reviews = reviews.exclude(grader__role="student").order_by(
                "-modification_date"
            )[:1]
            # TODO refactor: really hacky solution
            if reviews.first().question is not None:
                return GradeBaseComponentWise().compute_submission_grade(submission)
        return self.aggregate([self.compute_grade_by_review(r) for r in reviews])

    def get_submission_grading_method(self, submission):
        if submission.components.filter(question__category=MULTIPLECHOICE).exists():
            return "Quiz"

        reviews = submission.reviewassignment_set.filter(submitted=True)
        if not reviews.exists():
            return "Not graded"
        elif reviews.exclude(grader__role="student").exists():
            return "TA"
        else:
            return "Peer"


class AppealBase:
    @staticmethod
    def assign(submission):
        course = submission.assignment.course
        graders = CourseBase.get_graders(course.id)
        return graders[random.randint(0, len(graders) - 1)]

    @staticmethod
    def has_duplicate(submission):
        return Appeal._default_manager.filter(submission=submission).exists()

    @staticmethod
    def find(submission):
        return Appeal._default_manager.get(submission=submission)

    @staticmethod
    def get(apid):
        return Appeal._default_manager.filter(id=apid).first()

    @staticmethod
    def user_is_assignee(request, appeal):
        return request.user.id == appeal.assignee.id

    @staticmethod
    def find_by_assignee(user, cid):
        return Appeal._default_manager.filter(
            assignee__user=user, submission__assignment__course__id=cid
        ).order_by("status", "-creation_date")

    @staticmethod
    def find_pending_by_assignee(user, cid):
        return AppealBase.find_by_assignee(user, cid).exclude(
            status__in=[CLOSED, RESOLVED]
        )

    @staticmethod
    def find_by_author(user, cid):
        return Appeal._default_manager.filter(
            submission__author__user=user, submission__assignment__course__id=cid
        ).order_by("status", "-creation_date")

    @staticmethod
    def find_by_course(cid):
        return Appeal._default_manager.filter(
            submission__assignment__course__id=cid
        ).order_by("status", "-creation_date")


class FlagBase:
    @staticmethod
    def find_by_assignee(user, cid):
        return InaptReport._default_manager.filter(
            assignee__user=user, review__submission__assignment__course__id=cid
        ).order_by("closed", "-creation_date")
    
    @staticmethod
    def find_pending_by_assignee(user, cid):
        return FlagBase.find_by_assignee(user, cid).filter(
            closed=False
        )

    @staticmethod
    def find_by_author(user, cid):
        return InaptReport._default_manager.filter(
            reporter__user=user, review__submission__assignment__course__id=cid
        ).order_by("closed", "-creation_date")

    @staticmethod
    def find_by_course(cid):
        return InaptReport._default_manager.filter(
            review__submission__assignment__course__id=cid
        ).order_by("closed", "-creation_date")


if getattr(settings, "COMPONENTWISE_GRADE", False):
    GradeBase = GradeBaseComponentWise()
else:
    GradeBase = GradeBaseReviewsFirst()
