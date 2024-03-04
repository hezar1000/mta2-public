from django.db import models

from peer_assignment.models import AssignmentSubmission
from peer_course.models import CourseMember
from peer_review.models import ReviewAssignment
from .choices import APPEAL_STATUS_CHOICES, CLOSED, RESOLVED, INPROGRESS

from django.core.validators import *


class Appeal(models.Model):
    """
    A request made by a student in order to appeal their grade

    The status can be one of open, in-progress, resolved, or closed (resolved and closed have become synonymous)
    """

    submission = models.OneToOneField(AssignmentSubmission, on_delete=models.CASCADE)
    assignee = models.ForeignKey(CourseMember, on_delete=models.CASCADE)
    # Should we set the min-max length here or as a field on each Course?
    request = models.TextField(
        blank=False, validators=[MaxLengthValidator(3000), MinLengthValidator(300)]
    )
    response = models.TextField(blank=True, null=True, default=None)

    status = models.IntegerField(choices=APPEAL_STATUS_CHOICES, db_index=True)

    creation_date = models.DateTimeField(auto_now_add=True, db_index=True)
    modification_date = models.DateTimeField(auto_now=True)
    timer = models.FloatField(blank=True, default=False, db_index=True)

    def can_be_modified(self):
        return self.status != CLOSED and self.status != RESOLVED

    def reopen(self):
        self.status = INPROGRESS
        self.save()

    def order_key(self):
        return (self.status, self.creation_date)


class InaptReport(models.Model):
    """
    Lets students report inappropriate reviews
    The TA then inspects the review and has the option to flag the review
    Flagged reviews will be taken down and won't count toward the grade
    The reviewer can still see their review and can see that it has been flagged
    """

    review = models.ForeignKey(ReviewAssignment, on_delete=models.CASCADE)
    reporter = models.ForeignKey(
        CourseMember, related_name="inapt_reporter", on_delete=models.CASCADE
    )
    assignee = models.ForeignKey(
        CourseMember, related_name="report_assignee", on_delete=models.CASCADE
    )
    reason = models.TextField(
        blank=False, validators=[MaxLengthValidator(2000), MinLengthValidator(200)]
    )
    closed = models.BooleanField(default=False, db_index=True)

    creation_date = models.DateTimeField(auto_now_add=True, db_index=True)
    modification_date = models.DateTimeField(auto_now=True)
    timer = models.FloatField(blank=True, default=False, db_index=True)

    def get_status_display(self):
        return "Closed" if self.closed else "Open"

    def order_key(self):
        return (self.closed, self.creation_date)


class InaptFlag(models.Model):
    """
    The TAs can flag reviews as inappropriate
    Flagged reviews will be taken down and won't count toward the grade
    The reviewer can still see their review and can see that it has been flagged
    """

    review = models.OneToOneField(
        ReviewAssignment, related_name="flag", on_delete=models.CASCADE
    )
    reporter = models.ForeignKey(
        CourseMember, related_name="flagger", on_delete=models.CASCADE
    )
    reason = models.TextField(
        blank=False, validators=[MaxLengthValidator(200), MinLengthValidator(4)]
    )
    creation_date = models.DateTimeField(auto_now_add=True, db_index=True)
    modification_date = models.DateTimeField(auto_now=True)


class GradingItem(models.Model):
    gradee = models.ForeignKey(
        CourseMember, related_name="gradee", on_delete=models.CASCADE
    )

    grade_type = models.TextField(blank=True, null=True, default="[unspecified]") # assignment or peer review or participation, etc.?

    grading_period = models.TextField(blank=True, null=True, default="[unspecified]") # which week?

    grade = models.FloatField(default=0)

    max_grade = models.FloatField(default=0)

    grading_method = models.TextField(blank=True, null=True, default="[ungraded]") # TA or Peer?

    comments = models.TextField(blank=True, null=True, default=None) # aditional comments



