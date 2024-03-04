from django.db import models
from django.utils import timezone

from peer_review.models import AssignmentWithReviews

# Create your models here.


class EvaluationAssignment(models.Model):
    """The review of a review, done (usually) by a TA"""

    review = models.ForeignKey(
        "peer_review.ReviewAssignment",
        on_delete=models.CASCADE,
        related_name="evaluations",
    )

    grader = models.ForeignKey("peer_course.CourseMember", on_delete=models.CASCADE)

    # is_groundtruth= models.BooleanField("is_groundtruth?", default=False, db_column='is_groundtruth')

    nopublicuse = models.BooleanField(
        "Check this if you do not want your evaluation submission to be used anonymously in public.",
        default=False,
        db_column="noPublicUse",
    )

    submitted = models.BooleanField(blank=True, default=False, db_index=True)

    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    
    timer = models.FloatField(blank=True, default=0.0, db_index=True)

    # rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE)

    # review_content = models.TextField("Review Content", db_column='review_content', blank=True)

    class Meta:
        db_table = "evaluation_assignment"
        unique_together = ("review", "grader")

    def __str__(self):
        return "Evaluation of <%s>, by <%s>" % (self.review, self.grader)

    def deadline_passed(self):
        deadline = self.deadline()
        if deadline is None:
            return False
        return deadline < timezone.now()

    def deadline(self):
        # TODO maybe do it more efficiently?
        try:
            settings = (
                self.review.submission.assignment.assignmentwithreviews.evaluationsettings
            )
        except AssignmentWithReviews.DoesNotExist:
            return None
        except EvaluationSettings.DoesNotExist:
            return None

        return settings.student_evaluation_deadline_default

        # if self.grader.role == 'student':# CourseBase.is_student(self.grader, self.submission.assignment.course.id):
        #     return settings.student_review_deadline_default
        # else:  # Everyone except the students
        #     return settings.ta_review_deadline_default


class EvaluationContent(models.Model):
    """
    The result of the evaluation per submission component
    """

    evaluation = models.ForeignKey(
        EvaluationAssignment, on_delete=models.CASCADE, related_name="contents"
    )

    submission_component = models.ForeignKey(
        "peer_assignment.SubmissionComponent", on_delete=models.CASCADE
    )

    choice = models.ForeignKey(
        "peer_review.RubricQuestionMultipleChoiceItem", on_delete=models.CASCADE
    )

    reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "evaluation_content"
        # TODO: check how we can enforce constraints
        # unique_together = ('review_assignment', 'choice__question', 'submission_component')

    def __str__(self):
        return "%s, %s, %s" % (self.evaluation, self.choice.question, self.choice.id)

    def assigned_grade(self):
        return self.choice.marks


class EvaluationSettings(models.Model):
    """
    Defines to a subset of configurations in an assignment that correspond to the evaluation step
    """

    awr = models.OneToOneField(
        "peer_review.AssignmentWithReviews", on_delete=models.CASCADE, primary_key=True
    )

    # why default? :(
    # student_evaluation_release_time_default = models.DateTimeField("Default Release Time for Student evaluations", db_column='student_evaluation_release_time_default', null=True)

    student_evaluation_deadline_default = models.DateTimeField(
        "Default Deadline for Student evaluations",
        db_column="student_evaluation_deadline_default",
        null=True,
    )

    # ta_evaluation_release_time_default = models.DateTimeField("Default Release Time for TA evaluations", db_column='ta_evaluation_release_time_default', null=True)

    # TODO: do the we need this for TAs too?
    # ta_evaluation_deadline_default = models.DateTimeField("Default Deadline for TA evaluations", db_column='ta_evaluation_deadline_default', null=True)

    class Meta:
        db_table = "evaluation_settings"

    def __str__(self):
        return "Evaluation settings for %s" % self.awr.assignment

    # def ta_deadline_passed(self):
    #     if self.ta_review_deadline_default is None:
    #         return False
    #     return self.ta_review_deadline_default < timezone.now()
