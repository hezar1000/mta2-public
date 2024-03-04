from __future__ import unicode_literals
from random import randint
import datetime
import random
import string
import math
import os

from django.db import models
from django.utils import timezone
from django.db.models.aggregates import Count
from django.db.models.signals import pre_save
from django.db.models import Max
from django.dispatch import receiver
import datetime


from peer_review.choices import (
    QUESTION_TYPE_CHOICES,
    ASSGN_TYPE_CHOICES,
    PDF,
    QUIZ_ASGN,
)
from peer_course.models import Course, CourseMember


def create_random_string(length=30):
    if length <= 0:
        length = 30

    symbols = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join([random.choice(symbols) for x in range(length)])


def upload_to(instance, filename):
    now = timezone.now()
    filename_base, filename_ext = os.path.splitext(filename)
    return "target/{}_{}{}".format(
        now.strftime("%Y/%m/%d/%Y%m%d%H%M%S"),
        create_random_string(),
        filename_ext.lower(),
    )


class Assignment(models.Model):
    """
    Corresponds to a homework assigned in a specific course

     There are different types of assignments (quiz, PDF, text, ...)
     The instructor can set `grace_hours` which are soft deadline extensions
    as well as `max_late_units` that the student can hand-in the assignment late (in hours/days)
    """

    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    name = models.CharField("Display Name", db_column="name", max_length=128)

    browsable = models.BooleanField(
        "Visible to students",
        db_column="visible",
        default=False,
        blank=True,
        db_index=True,
    )

    release_time = models.DateTimeField(
        "Release Time", db_column="release_time", blank=True, null=True, default=None
    )

    deadline = models.DateTimeField(
        "Deadline",
        db_column="deadline",
        blank=True,
        null=True,
        default=None,
        db_index=True,
    )
    """After the deadline, students can no longer submit or revise."""

    ## TODO: we may need to store the creation dates for sorting
    # creation_date = models.DateTimeField(auto_now_add=True)
    # modification_time = models.DateTimeField(auto_now=True)

    max_late_units = models.PositiveIntegerField(
        "Max Late Days allowed", blank=True, default=0
    )

    grace_hours = models.FloatField("# of Grace hours", blank=True, default=0)

    max_attempts = models.PositiveIntegerField(blank=True, null=True, default=None)
    """# not used normally ..."""

    qualification_grade = models.FloatField(blank=True, null=True, default=None)

    submission_required = models.BooleanField(blank=True, default=True)

    # students who have made submissions for this assignment.
    # TODO: why do we need this? removing for now
    # authors = models.ManyToManyField(User, through='AssignmentSubmission')

    assignment_type = models.CharField(
        "Type",
        db_column="assignment_type",
        choices=ASSGN_TYPE_CHOICES,
        default=PDF,
        max_length=16,
    )
    """
    Right now we have 3 different types of assignments:
        - PDF: the statement is uploaded as a PDF
               Also requires to know the number of questions in the PDF
        - Quiz: a set of multiple-choice questions
        - Text: questions with a text as output, e.g an essay
    """

    statement = models.FileField(
        "Statement", upload_to="uploads/statements", blank=True, null=True
    )

    max_total_grade = models.FloatField(default=0, blank=True)
    "Maximum grade possible in this assignment"

    # This was used to set a password for each assignment.
    # passwordmessage = models.TextField("Password Message", db_column='passwordMessage', blank=True, null=True)
    # password = models.CharField(max_length=255, blank=True, null=False)

    class Meta:
        db_table = "assignment"

    def __str__(self):
        if self.pk is None:
            return "New assignment"
        questions = str()
        for q in self.questions.all():
            questions.join(str(q) + ", ")
        # print(questions)
        return "Course: %s, Assignment: %s" % (self.course.displayname, self.name)

    def deadline_passed(self):
        # TODO: check where this is used
        if self.deadline is None:
            return False
        return self.deadline < timezone.now()

    def time_until_deadline_passed(self):
        deadline = self.deadline
        if deadline is None:
            return False
        remaining_time= deadline - timezone.now()
        rounded_remaining_time = remaining_time - datetime.timedelta(microseconds=remaining_time.microseconds)
        return rounded_remaining_time

    def populate_max_grade(self):
        # TODO: check to see if using a single query is better here or not
        if self.assignment_type == QUIZ_ASGN:
            self.max_total_grade = sum(
                [
                    q.choices.aggregate(Max("marks")).get("marks__max", 0)
                    for q in self.questions.all()
                ]
            )
        else:
            self.max_total_grade = sum(
                [
                    q.rubric.max_total_grade() if q.rubric else 0
                    for q in self.questions.all()
                ]
            )

    def can_compose_submission(self, author):
        return author.can_compose_submission(assignment=self)

    def grace_deadline(self):
        if self.deadline is None:
            return None
        return self.deadline + datetime.timedelta(hours=self.grace_hours)

    def grace_deadline_passed(self):
        if self.deadline is None:
            return None
        return self.grace_deadline() < timezone.now()

    def hard_deadline(self):
        """
            Hard deadline for submitting this assignment for all students.

            ** This might be a little different for each student (based on used late units)
            therefore, it should not be used for calculating `can_compose_submission`
        """
        if self.deadline is None:
            return None
        return self.grace_deadline() + datetime.timedelta(days=self.max_late_units)

    def calculate_late_units_now(self):
        now = timezone.now()
        if now > self.grace_deadline():
            delta = now - self.grace_deadline()
            return math.ceil(delta.total_seconds() / 60 / 60 / 24)
        else:
            return 0

    def _role_reviews_count(self, role):
        from peer_review.models import ReviewAssignment

        return (
            ReviewAssignment._default_manager.filter(submission__assignment=self)
            .filter(grader__role=role)
            .count()
        )

    def instructor_reviews_count(self):
        return self._role_reviews_count("instructor")

    def ta_reviews_count(self):
        return self._role_reviews_count("ta")

    def student_reviews_count(self):
        return self._role_reviews_count("student")

    def get_review_settings(self):
        from peer_review.models import AssignmentWithReviews

        try:
            awr = self.assignmentwithreviews
            return awr
        except AssignmentWithReviews.DoesNotExist:
            return None


class AssignmentQuestion(models.Model):
    """
    Corresponds to questions in assignments

    There are multiple question types: multiple-choice, text, file-upload
    The question types should (somehow loosely) match the assignment type
    """

    assignment = models.ForeignKey(
        Assignment, related_name="questions", on_delete=models.CASCADE
    )

    rubric = models.ForeignKey(
        "peer_review.Rubric", blank=True, null=True, on_delete=models.PROTECT
    )

    # peer_evaluation: review of reviews
    evaluation_rubric = models.ForeignKey(
        "peer_review.Rubric",
        related_name="evaluated_question",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
    )

    title = models.CharField("Question Title", max_length=128)

    description = models.TextField("Question Description")

    category = models.CharField(
        "Question Type",
        db_column="question_type",
        default="NONE",
        choices=QUESTION_TYPE_CHOICES,
        max_length=128,
        db_index=True,
    )

    class Meta:
        db_table = "assignment_question"

    def __str__(self):
        return "%s: %s [Using the rubric: %s]" % (
            self.title,
            self.description,
            self.rubric,
        )


class AssignmentQuestionMultipleChoice(models.Model):
    """Specifies each choice in an multiple-choice question"""

    question = models.ForeignKey(
        AssignmentQuestion, on_delete=models.CASCADE, related_name="choices"
    )

    choice_text = models.TextField("Item Description")

    marks = models.IntegerField("Number of Marks", default=0, blank=True)

    class Meta:
        db_table = "assignment_question_multiple_choice"

    def __str__(self):
        return "%s,%s,%s" % (self.question, self.choice_text, self.marks)


# Store files for an assignment question
# class AssignmentFile(models.Model):
#     assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)

#     # attachment = models.FileField(upload_to='target/', db_column='file')
#     attachment = models.FileField("Attachment", db_column='file')

#     def filename(self):
#         return os.path.basename(self.attachment.name)

#     class Meta:
#         db_table = 'assignment_file'


# The assignment submission
class AssignmentSubmission(models.Model):
    """
    Corresponds to submissions of the assignment (by students usually)

    Callibration submissions are submissions created by the staff and reviewed by students
    in order to get them "calibrated", i.e. move up to the independent pool
    """

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)

    # User who authored this submission
    author = models.ForeignKey(
        CourseMember, related_name="submissions_authored", on_delete=models.CASCADE
    )

    nopublicuse = models.BooleanField(
        "Check this if you do not want your submission to be used anonymously in public.",
        db_column="noPublicUse",
    )

    calibration_id = models.IntegerField(
        "calibration_id",
        db_column="calibration_id",
        default=0,
        blank=True,
        db_index=True,
    )

    time_submitted = models.DateTimeField(
        "Time submitted", auto_now_add=True, db_index=True
    )

    time_last_modified = models.DateTimeField(auto_now=True)

    late_units_used = models.PositiveIntegerField(blank=True, default=0)

    attempts = models.PositiveIntegerField(blank=True, default=1)

    final_grade = models.FloatField(blank=True, null=True, default=None)
    final_grading_method = models.TextField(blank=True, null=True, default="[ungraded]")

    spotchecking_priority= models.FloatField("Spotchecking Priority", db_column='spotcheckingpriority', default=1000)
#    is_appealed = models.BooleanField("is_appealed?", db_column="is_appealed", default=False, db_index=True)

    class Meta:
        db_table = "assignment_submission"
        unique_together = ("assignment", "author", "calibration_id")

    def is_edited(self):
        return self.time_submitted != self.time_last_modified

    def __str__(self):
        return "Submission for assignment %s with Calibration id= %s by %s %s" % (
            self.assignment,
            self.calibration_id,
            self.author.user.first_name,
            self.author.user.last_name,
        )

    def populate_grade(self):
        from peer_grade.base import GradeBase

        self.final_grade = GradeBase.compute_submission_grade(self)
        self.final_grading_method = GradeBase.get_submission_grading_method(self)

    def get_review_settings(self):
        return self.assignment.get_review_settings()

    def get_appeal(self):
        from peer_grade.models import Appeal

        try:
            return self.appeal
        except Appeal.DoesNotExist:
            return None

    def ta_deadline_passed(self):
        awr = self.get_review_settings()
        if awr:
            return awr.ta_deadline_passed()
        return False
    
    def student_deadline_passed(self):
        awr = self.get_review_settings()
        if awr:
            return awr.student_deadline_passed()
        return False

    def can_compose_submission(self):
        return self.author.can_compose_submission(self)


# multiple submission components form a submission
class SubmissionComponent(models.Model):
    """
    Each submission components corresponds to the solution provided by
    a student to one specific question in the assignment. Therefore,
    each submission usually consists of many submission components
    """

    submission = models.ForeignKey(
        "AssignmentSubmission", related_name="components", on_delete=models.CASCADE
    )

    question = models.ForeignKey(AssignmentQuestion, on_delete=models.CASCADE)

    content = models.TextField("Content", db_column="content")

    attachment = models.FileField(
        blank=True, null=True, default=None, upload_to="assignment_submission_files/"
    )

    manual_grade = models.FloatField(blank=True, null=True, default=None)
    ta_review_grade = models.FloatField(blank=True, null=True, default=None)
    automatic_grade = models.FloatField(blank=True, null=True, default=None)

    class Meta:
        db_table = "submission_component"
        unique_together = ("submission", "question")

    def __str__(self):
        return "%s,%s" % (self.submission, self.question)

    def final_grade(self):
        # TODO................
        from peer_grade.base import (
            GradeBase,
        )  # doing it this way to avoid cyclic-dependency

        return GradeBase.compute_submission_component_grade(self)

    def final_grading(self):
        """
            grade + method

            Returns: Object of the form:
                {
                    'grade': value or None,
                    'method': one of('Manual', 'TA', 'Peer', None: when grade is None),
                }
        """
        # TODO................
        from peer_grade.base import (
            GradeBase,
        )  # doing it this way to avoid cyclic-dependency

        return GradeBase.compute_submission_component_grading(self)

        # TODO: check if we need to redo the automatic grading lazily
        # if self.manual_grade is not None:
        #     return self.manual_grade
        # elif self.ta_review_grade is not None:
        #     return self.ta_review_grade
        # else:
        #     return self.automatic_grade


# class JobNotifications(models.Model):
#     notificationid = models.IntegerField(db_column='notificationID', primary_key=True, blank=True, null=False)
#     courseid = models.IntegerField(db_column='courseID')
#     assignmentid = models.IntegerField(db_column='assignmentID')
#     job = models.TextField()
#     dateran = models.DateTimeField(db_column='dateRan')
#     success = models.BooleanField()  # This field type is a guess.
#     seen = models.BooleanField()  # This field type is a guess.
#     summary = models.TextField()
#     details = models.TextField()  # This field type is a guess.

#     class Meta:
#         db_table = 'job_notifications'

# class Status(models.Model):
#     value = models.TextField(primary_key=True, blank=True, null=False)

#     class Meta:
#         managed = False
#         db_table = 'status'


# class AppealAssignment(models.Model):
#     submissionid = models.IntegerField(db_column='submissionID', primary_key=True, blank=True, null=False)
#     markerid = models.IntegerField(db_column='markerID')

#     class Meta:
#         db_table = 'appeal_assignment'

# class Appealtype(models.Model):
#     value = models.TextField(primary_key=True, blank=True, null=False)

#     class Meta:
#         db_table = 'appealType'

# class AssignmentPasswordEntered(models.Model):
#     userid = models.IntegerField(db_column='userID', primary_key=True)
#     assignmentid = models.IntegerField(db_column='assignmentID', primary_key=True)
#     class Meta:
#         db_table = 'assignment_password_entered'
#         unique_together = (('userid', 'assignmentid'),)

# We do not need the group picker type of assignment anymore.
# class GroupPickerAssignment(models.Model):
#     assignmentid = models.IntegerField(db_column='assignmentID', primary_key=True, blank=True, null=False)
#     startdate = models.DateTimeField(db_column='startDate')
#     stopdate = models.DateTimeField(db_column='stopDate')

#     class Meta:
#         db_table = 'group_picker_assignment'

# class GroupPickerAssignmentGroups(models.Model):
#     assignmentid = models.IntegerField(db_column='assignmentID', primary_key=True) # should reference the assignmentID column in the table "assignments"
#     groupindex = models.IntegerField(db_column='groupIndex', primary_key=True)
#     grouptext = models.TextField(db_column='groupText')

#     class Meta:
#         db_table = 'group_picker_assignment_groups'
#         unique_together = (('assignmentid', 'groupindex'),)

# class GroupPickerAssignmentSelections(models.Model):
#     selectionid = models.IntegerField(db_column='selectionID', primary_key=True, blank=True, null=False)
#     assignmentid = models.IntegerField(db_column='assignmentID')
#     userid = models.IntegerField(db_column='userID')
#     groupindex = models.IntegerField(db_column='groupIndex')

#     class Meta:
#         db_table = 'group_picker_assignment_selections'
#         unique_together = (('assignmentid', 'userid'),)


# class PeerReviewAssignmentIndependent(models.Model):
#     userid = models.IntegerField(db_column='userID', primary_key=True)
#     assignmentid = models.IntegerField(db_column='assignmentID', primary_key=True)
#     class Meta:
#         db_table = 'peer_review_assignment_independent'
#         unique_together = (('userid', 'assignmentid'),)

# class PeerReviewAssignmentDenied(models.Model):
#     userid = models.IntegerField(db_column='userID', primary_key=True)
#     assignmentid = models.IntegerField(db_column='assignmentID', primary_key=True)
#     class Meta:
#         db_table = 'peer_review_assignment_denied'
#         unique_together = (('userid', 'assignmentid'),)


@receiver(pre_save, sender=Assignment)
def save_assignment(sender, instance, **kwargs):
    instance.populate_max_grade()
