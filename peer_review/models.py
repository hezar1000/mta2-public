from django.db import models
from django.db.models import Max
from django.utils import timezone
from peer_assignment.models import Assignment, AssignmentSubmission, AssignmentQuestion
from peer_course.base import CourseBase
from peer_course.models import CourseMember
from .choices import *
import datetime



class RubricQuestion(models.Model):
    """
    Defines a question that the reviewer/evaluator must answer when reviewing the submission/review

    Different choices specify different grades and the grader must is also required to write down his/her reasoning
    """

    title = models.CharField(
        "Question Title", db_column="question_title", max_length=128
    )

    text = models.CharField(
        "Question Description", db_column="question_text", max_length=1000
    )

    min_reason_length = models.PositiveIntegerField(
        "Min Length of Reasoning field", default=20
    )
    max_reason_length = models.PositiveIntegerField(
        "Max Length of Reasoning field", default=500
    )

    # category = models.CharField("Question Type",
    #     db_column='question_type',
    #     choices=QUESTION_TYPE_CHOICES,
    #     default="NONE",
    #     max_length=128)

    class Meta:
        db_table = "rubric_question"

    def __str__(self):
        return "%s" % (self.title)

    def max_grade(self):
        return self.choices.all().aggregate(Max("marks"))["marks__max"] or 0

    def safe_to_remove(self):
        return not ReviewContent._default_manager.filter(choice__question=self).exists()


# TODO: We don't need this ....
class ValidationRule(models.Model):

    rubric_question = models.ForeignKey(RubricQuestion, on_delete=models.CASCADE)

    rule_type = models.CharField(
        "Rule Type",
        db_column="rule_type",
        choices=VALIDATION_RULE_TYPE_CHOICES,
        default="NONE",
        max_length=128,
    )

    rule_content = models.TextField("Rule Content", db_column="rule_content")

    class Meta:
        db_table = "rubric_validation_rule"

    def __str__(self):
        return "%s,%s,%s" % (self.rubric_question, self.rule_type, self.rule_content)


class RubricQuestionMultipleChoiceItem(models.Model):
    """Defines the possible answers to the rubric question. Also defines its grade."""

    question = models.ForeignKey(
        RubricQuestion, related_name="choices", on_delete=models.CASCADE
    )

    text = models.CharField("Item Description", db_column="item_text", max_length=1000)

    marks = models.FloatField(
        "Number of Marks", db_column="item_marks", default=0, blank=True
    )

    class Meta:
        db_table = "rubric_question_multiple_choice_item"

    def __str__(self):
        return "%s,%s,%s" % (self.question, self.text, self.marks)


class Rubric(models.Model):
    """Defines a rubric: a set of questions that the grader must answer in order to grade each question"""

    name = models.CharField("Display Name", db_column="name", max_length=128)

    questions = models.ManyToManyField(RubricQuestion)

    class Meta:
        db_table = "rubric"

    def __str__(self):
        return "%s" % self.name

    def max_total_grade(self):
        return sum([q.max_grade() for q in self.questions.all()])


class AssignmentWithReviews(models.Model):
    "Defines to a subset of configurations in an assignment that correspond to the review step"

    assignment = models.OneToOneField(
        Assignment, to_field="id", on_delete=models.CASCADE, primary_key=True
    )

    # why default? :(
    # student_review_release_time_default = models.DateTimeField("Default Release Time for Student Reviews", db_column='student_review_release_time_default', null=True)

    student_review_deadline_default = models.DateTimeField(
        "Default Deadline for Student Reviews",
        db_column="student_review_deadline_default",
        null=True,
    )

    # ta_review_release_time_default = models.DateTimeField("Default Release Time for TA Reviews", db_column='ta_review_release_time_default', null=True)

    ta_review_deadline_default = models.DateTimeField(
        "Default Deadline for TA Reviews",
        db_column="ta_review_deadline_default",
        null=True,
    )
    """Default Deadline for TA Reviews"""

    ta_reviews_per_question = models.BooleanField(
        "Assign TA reviews per question", default=False
    )
    """Whether to assign TA reviews per question or per the whole assignment"""

    class Meta:
        db_table = "assignment_with_reviews"

    def __str__(self):
        return "Review settings for %s" % self.assignment

    def ta_deadline_passed(self):
        if self.ta_review_deadline_default is None:
            return False
        return self.ta_review_deadline_default < timezone.now()

    def student_deadline_passed(self):
        if self.student_review_deadline_default is None:
            return False
        return self.student_review_deadline_default < timezone.now()


class ReviewAssignment(models.Model):
    """
    This is the through model for a many-to-many relationship between AssignmentSubmission and User
    Each submission is graded by many users.  Each user grades many submissions.
    """

    submission = models.ForeignKey(AssignmentSubmission, on_delete=models.CASCADE)

    grader = models.ForeignKey(CourseMember, on_delete=models.CASCADE)

    question = models.ForeignKey(
        AssignmentQuestion, blank=True, null=True, on_delete=models.CASCADE
    )

    is_groundtruth = models.BooleanField(
        "is_groundtruth?", db_column="is_groundtruth", default=False, db_index=True
    )

    nopublicuse = models.BooleanField(
        "Check this if you do not want your review submission to be used anonymously in public.",
        default=False,
        db_column="noPublicUse",
    )

    submitted = models.BooleanField(blank=True, default=False, db_index=True)

    submission_date = models.DateTimeField(db_column="submission date", null=True, db_index=True, blank= True, default= None)

    creation_date = models.DateTimeField(auto_now_add=True, db_index=True)
    modification_date = models.DateTimeField(auto_now=True)

    assigned_grade = models.FloatField(default=0)
    markingload= models.FloatField("Review Marking Load", db_column='reviewmarkingload', null=True, default=1.0)
    visible = models.BooleanField(blank=True, default=True, db_index=True)

    endorsed= models.BooleanField(
        "endorsed?", db_column="endorsed", default=False, db_index=True
    )

    timer = models.FloatField(blank=True, default=0.0, db_index=True)
    # rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE)

    # review_content = models.TextField("Review Content", db_column='review_content', blank=True)

    class Meta:
        db_table = "review_assignment"
        unique_together = ("submission", "grader", "question")

    def __str__(self):
        return "%s,Calibration id: %s,%s,%s" % (
            self.submission.assignment,
            self.submission.calibration_id,
            self.submission.author.user,
            self.grader,
        )

    def deadline_passed(self):
        deadline = self.deadline()
        if deadline is None:
            return False
        return deadline < timezone.now()

    def time_until_deadline_passed(self):
        deadline = self.deadline()
        if deadline is None:
            return False
        remaining_time= deadline - timezone.now()
        rounded_remaining_time = remaining_time - datetime.timedelta(microseconds=remaining_time.microseconds)
        return rounded_remaining_time

    def deadline(self):
        try:
            awr = self.submission.assignment.assignmentwithreviews
        except AssignmentWithReviews.DoesNotExist:
            return None

        if (
            self.grader.role == "student"
        ):  # CourseBase.is_student(self.grader, self.submission.assignment.course.id):
            return awr.student_review_deadline_default
        else:  # Everyone except the students
            return awr.ta_review_deadline_default

    def evaluation_grade(self):
        from peer_grade.base import GradeBase

        return GradeBase.compute_review_evaluation(self)

    def max_evaluation_grade(self):
        from peer_grade.base import GradeBase

        return GradeBase.max_evaluation_grade(self.submission.assignment)

    # TODO: check to see if doing a query is better here
    def populate_grade(self):
        from peer_grade.base import GradeBase

        self.assigned_grade = GradeBase.compute_grade_by_review(self)


class ReviewContent(models.Model):
    """
    The result of the review per submission component
    """

    review_assignment = models.ForeignKey(ReviewAssignment, on_delete=models.CASCADE)

    submission_component = models.ForeignKey(
        "peer_assignment.SubmissionComponent", on_delete=models.CASCADE
    )

    choice = models.ForeignKey(
        RubricQuestionMultipleChoiceItem, on_delete=models.CASCADE
    )

    reason = models.TextField(blank=True, default="")

    is_reason_viewed = models.BooleanField(
        "is_reason_viewed?", db_column="is_reason_viewed", default=False, db_index=True
    )

    component_grade = models.FloatField(
        "component_wise_grade", db_column="component_wise_grade", default=0, blank=True
    )

    class Meta:
        db_table = "review_content"
        # TODO: check how we can enforce constraints
        # unique_together = ('review_assignment', 'choice__question', 'submission_component')

    def __str__(self):
        return "%s,%s,%s" % (
            self.review_assignment,
            self.choice.question,
            self.choice.id,
        )

    def assigned_grade(self):
        return self.choice.marks

    def populate_grade(self):
        self.component_grade = self.choice.marks


class ReviewContentFile(models.Model):
    """
    File attachment per ReviewContent object
    
    * UNUSED *
    """

    review_content = models.ForeignKey(ReviewContent, on_delete=models.CASCADE)

    attachment = models.FileField("Review Content File", db_column="file")

    class Meta:
        db_table = "review_content_file"


# class PeerReviewAssignment(models.Model):
#    submissionid = models.IntegerField(db_column='submissionID', primary_key=True, blank=True, null=False)
#    text = models.TextField()  # This field type is a guess.
#    topicindex = models.IntegerField(db_column='topicIndex', blank=True, null=False)

#    class Meta:
#        db_table = 'peer_review_assignment_essays'

# class AssignmentSettings(models.Model):

#
# This is taken care of by the browsable field in the assignment table.
#
# submissionstartdate = models.DateTimeField(db_column='submissionStartDate')

# After this date and time, the assignment becomes non-browsable automatically.
# deadline = models.DateTimeField(db_column='submissionDeadline')

# reviewstartdate = models.DateTimeField(db_column='reviewStartDate')
# reviewdeadline = models.DateTimeField(db_column='reviewDeadline')

#
# Perhaps we want to a separate table to manage grades and whether they are visible.
#
# markpostdate = models.DateTimeField(db_column='markPostDate')

#
# Should be part of the grading scheme.
#
# maxsubmissionscore = models.TextField(db_column='maxSubmissionScore')   # This field type is a guess.

#
# Should be part of the peer review component
#
# maxreviewscore = models.TextField(db_column='maxReviewScore')   # This field type is a guess.
# defaultnumberofreviews = models.IntegerField(db_column='defaultNumberOfReviews')
# allowrequestofreviews = models.TextField(db_column='allowRequestOfReviews')   # This field type is a guess.

#
# These options are about what information the students want to see.
# Perhaps this should be controlled by the students?
# They could toggle what they want to see what they don't want to see.
#
# showmarksforreviewsreceived = models.BooleanField("Show the marks and comments for the submission", db_column='showMarksForReviewsReceived')   # This field type is a guess.
# showotherreviewsbystudents = models.BooleanField("Show the other student reviews", db_column='showOtherReviewsByStudents')   # This field type is a guess.
# showotherreviewsbyinstructors = models.BooleanField("Show instructor reviews", db_column='showOtherReviewsByInstructors')   # This field type is a guess.
# showmarksforotherreviews = models.BooleanField("Show the marks and comments for other reviews of the submission", db_column='showMarksForOtherReviews')   # This field type is a guess.
# showmarksforreviewedsubmissions = models.BooleanField(db_column='showMarksForReviewedSubmissions')   # This field type is a guess.

#
# Whether or not to display the review status of the current student for this assignment.
#
# showpoolstatus = models.BooleanField(db_column='showPoolStatus')

#
# Appeal functionalities
#
# appealdeadline = models.DateTimeField(db_column='appealDeadline')

#
# Calibration info should go somewhere else.
#
# calibrationstartdate = models.DateTimeField(db_column='calibrationStartDate')
# calibrationdeadline = models.DateTimeField(db_column='calibrationDeadline')
# extracalibrations = models.IntegerField(db_column='extraCalibrations', blank=True, null=False)
# calibrationmincount = models.IntegerField(db_column='calibrationMinCount')
# calibrationmaxscore = models.IntegerField(db_column='calibrationMaxScore')
# calibrationthresholdmse = models.TextField(db_column='calibrationThresholdMSE')   # This field type is a guess.
# calibrationthresholdscore = models.TextField(db_column='calibrationThresholdScore')   # This field type is a guess.

#
# Specific things about essay assignment that we are not using anymore.
#
# autoassignessaytopic = models.TextField(db_column='autoAssignEssayTopic')   # This field type is a guess.
# essaywordlimit = models.IntegerField(db_column='essayWordLimit')

# class Meta:
#     db_table = 'assignment_settings'


# Assignment type is essay.
# class PeerReviewAssignmentEssays(models.Model):
#    submissionid = models.IntegerField(db_column='submissionID', primary_key=True, blank=True, null=False)
#    text = models.TextField()  # This field type is a guess.
#    topicindex = models.IntegerField(db_column='topicIndex', blank=True, null=False)

#    class Meta:
#        db_table = 'peer_review_assignment_essays'

# class PeerReviewAssignmentEssaySettings(models.Model):
#    assignmentid = models.IntegerField(db_column='assignmentID', primary_key=True)
#    topicindex = models.IntegerField(db_column='topicIndex', primary_key=True)
#    topic = models.CharField(max_length=255)
#    class Meta:
#        db_table = 'peer_review_assignment_essay_settings'
#        unique_together = (('assignmentid', 'topicindex'),)

# Assignment type is article response.
# class PeerReviewAssignmentArticleResponses(models.Model):
#    submissionid = models.IntegerField(db_column='submissionID', primary_key=True, blank=True, null=False)
#    articleindex = models.IntegerField(db_column='articleIndex')
#    outline = models.TextField()  # This field type is a guess.
#    response = models.TextField()  # This field type is a guess.

#    class Meta:
#        db_table = 'peer_review_assignment_article_responses'

# class PeerReviewAssignmentArticleResponseSettings(models.Model):
#    assignmentid = models.IntegerField(db_column='assignmentID', primary_key=True)
#    articleindex = models.IntegerField(db_column='articleIndex', primary_key=True)
#    name = models.CharField(max_length=255)
#    link = models.TextField()
#    class Meta:
#        db_table = 'peer_review_assignment_article_response_settings'
#        unique_together = (('assignmentid', 'articleindex'),)


# Assignment type is images.
# class PeerReviewAssignmentImages(models.Model):
#    submissionid = models.IntegerField(db_column='submissionID', primary_key=True, blank=True, null=False)
#    imgwidth = models.IntegerField(db_column='imgWidth')
#    imgheight = models.IntegerField(db_column='imgHeight')
#    imgdata = models.TextField(db_column='imgData')   # This field type is a guess.
#    text = models.TextField()

#    class Meta:
#        db_table = 'peer_review_assignment_images'

# Assignment type is code.
# class PeerReviewAssignmentCode(models.Model):
#    submissionid = models.IntegerField(db_column='submissionID', primary_key=True, blank=True, null=False)
#    code = models.TextField()  # This field type is a guess.

#    class Meta:
#        db_table = 'peer_review_assignment_code'


# class PeerReviewAssignmentCodeSettings(models.Model):
#    assignmentid = models.IntegerField(db_column='assignmentID', primary_key=True, blank=True, null=False)
#    codelanguage = models.CharField(db_column='codeLanguage', max_length=255)
#    codeextension = models.CharField(db_column='codeExtension', max_length=10)
#    uploadonly = models.TextField(db_column='uploadOnly')   # This field type is a guess.

#    class Meta:
#        db_table = 'peer_review_assignment_code_settings'


# class PeerReviewAssignmentQuestions(models.Model):
#     questionid = models.IntegerField(db_column='questionID', primary_key=True, blank=True, null=False)
#     assignmentid = models.IntegerField(db_column='assignmentID')
#     questionname = models.CharField(db_column='questionName', max_length=128)
#     questiontext = models.TextField(db_column='questionText')
#     questiontype = models.CharField(db_column='questionType', max_length=64)
#     hidden = models.TextField()  # This field type is a guess.
#     displaypriority = models.IntegerField(db_column='displayPriority')

#     class Meta:
#         db_table = 'peer_review_assignment_questions'

# class ReviewRadioOptions(models.Model):
#     questionid = models.IntegerField(db_column='questionID', primary_key=True)
#     index = models.IntegerField(primary_key=True)
#     label = models.CharField(max_length=1024)
#     score = models.TextField()  # This field type is a guess.

#     class Meta:
#         db_table = 'peer_review_assignment_radio_options'
#         unique_together = (('questionid', 'index'),)

# class PeerReviewAssignmentReviewAnswers(models.Model):
#     matchid = models.IntegerField(db_column='matchID', primary_key=True)
#     questionid = models.IntegerField(db_column='questionID', primary_key=True)
#     answerint = models.IntegerField(db_column='answerInt', blank=True, null=False)
#     answertext = models.TextField(db_column='answerText', blank=True, null=False)
#     reviewtimestamp = models.DateTimeField(db_column='reviewTimestamp')

#     class Meta:
#         db_table = 'peer_review_assignment_review_answers'
#         unique_together = (('matchid', 'questionid'),)


# class PeerReviewAssignmentReviewAnswersDrafts(models.Model):
#     matchid = models.IntegerField(db_column='matchID', primary_key=True)
#     questionid = models.IntegerField(db_column='questionID', primary_key=True)
#     answerint = models.IntegerField(db_column='answerInt', blank=True, null=False)
#     answertext = models.TextField(db_column='answerText', blank=True, null=False)

#     class Meta:
#         db_table = 'peer_review_assignment_review_answers_drafts'
#         unique_together = (('matchid', 'questionid'),)


# class Calibrationstate(models.Model):
#     value = models.TextField(primary_key=True, blank=True, null=False)

#     class Meta:
#         db_table = 'calibrationState'


# class PeerReviewAssignmentAppealMessages(models.Model):
#     appealmessageid = models.IntegerField(db_column='appealMessageID', primary_key=True, blank=True, null=False)
#     appealtype = models.TextField(db_column='appealType')
#     matchid = models.IntegerField(db_column='matchID')
#     authorid = models.IntegerField(db_column='authorID')
#     viewedbystudent = models.TextField(db_column='viewedByStudent')   # This field type is a guess.
#     text = models.TextField()


# class PeerReviewAssignmentCalibrationMatches(models.Model):
#     matchid = models.IntegerField(db_column='matchID', primary_key=True, blank=True, null=False)
#     assignmentid = models.IntegerField(db_column='assignmentID')
#     required = models.TextField()  # This field type is a guess.

#     class Meta:
#         db_table = 'peer_review_assignment_calibration_matches'

# class PeerReviewAssignmentCalibrationPools(models.Model):
#     assignmentid = models.IntegerField(db_column='assignmentID', primary_key=True)
#     poolassignmentid = models.IntegerField(db_column='poolAssignmentID', primary_key=True)

#     class Meta:
#         db_table = 'peer_review_assignment_calibration_pools'
#         unique_together = (('assignmentid', 'poolassignmentid'),)


# class PeerReviewAssignmentDemotionLog(models.Model):
#     userid = models.IntegerField(db_column='userID', primary_key=True, blank=True, null=False)
#     demotiondate = models.DateTimeField(db_column='demotionDate')
#     demotionthreshold = models.TextField(db_column='demotionThreshold')   # This field type is a guess.

#     class Meta:
#         db_table = 'peer_review_assignment_demotion_log'

# class PeerReviewAssignmentInstructorReviewTouchTimes(models.Model):
#     submissionid = models.IntegerField(db_column='submissionID', primary_key=True)
#     instructorid = models.IntegerField(db_column='instructorID', primary_key=True)
#     timestamp = models.DateTimeField()

#     class Meta:
#         db_table = 'peer_review_assignment_instructor_review_touch_times'
#         unique_together = (('submissionid', 'instructorid'),)


# class PeerReviewAssignmentMatches(models.Model):
#     matchid = models.IntegerField(db_column='matchID', primary_key=True, blank=True, null=False)
#     submissionid = models.IntegerField(db_column='submissionID')
#     reviewerid = models.IntegerField(db_column='reviewerID')
#     instructorforced = models.TextField(db_column='instructorForced')   # This field type is a guess.
#     calibrationstate = models.TextField(db_column='calibrationState')

#     class Meta:
#         db_table = 'peer_review_assignment_matches'
#         unique_together = (('submissionid', 'reviewerid'),)

# class PeerReviewAssignmentReviewMarks(models.Model):
#     matchid = models.IntegerField(db_column='matchID', primary_key=True, blank=True, null=False)
#     score = models.TextField()  # This field type is a guess.
#     comments = models.TextField(blank=True, null=False)
#     automatic = models.TextField()  # This field type is a guess.
#     reviewpoints = models.TextField(db_column='reviewPoints')   # This field type is a guess.
#     reviewmarktimestamp = models.DateTimeField(db_column='reviewMarkTimestamp')

#     class Meta:
#         db_table = 'peer_review_assignment_review_marks'


# class PeerReviewAssignmentSpotChecks(models.Model):
#     submissionid = models.IntegerField(db_column='submissionID', primary_key=True, blank=True, null=False)
#     checkerid = models.IntegerField(db_column='checkerID')
#     status = models.TextField()

#     class Meta:
#         db_table = 'peer_review_assignment_spot_checks'


# class PeerReviewAssignmentSubmissionMarks(models.Model):
#     submissionid = models.IntegerField(db_column='submissionID', primary_key=True, blank=True, null=False)
#     score = models.TextField()  # This field type is a guess.
#     comments = models.TextField(blank=True, null=False)
#     automatic = models.TextField()  # This field type is a guess.
#     submissionmarktimestamp = models.DateTimeField(db_column='submissionMarkTimestamp')

#     class Meta:
#         managed = False
#         db_table = 'peer_review_assignment_submission_marks'


# class PeerReviewAssignmentTextOptions(models.Model):
#     questionid = models.IntegerField(db_column='questionID', primary_key=True, blank=True, null=False)
#     minlength = models.IntegerField(db_column='minLength')


#     class Meta:
#         managed = False
#         db_table = 'peer_review_assignment_text_options'
