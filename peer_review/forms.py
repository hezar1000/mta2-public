from django import forms
from django.forms import ModelForm
from django.core import validators
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from django.utils import timezone

from .models import *
from .choices import *
from .utils import *
from .base import ReviewBase
from .base_forms import AssignmentSettingsForm, ChoicesForm, AssignTAsForm
from peer_assignment.models import SubmissionComponent
from peer_home.popup_widgets import SelectWithPop, MultipleSelectWithPop

from peer_course.base import CourseBase
from peer_course.models import CourseMember

import re, datetime


class AssignmentWithReviewsForm(AssignmentSettingsForm):
    class Meta:
        model = AssignmentWithReviews
        fk_name = "Assignment"
        fields = [
            "student_review_deadline_default",
            "ta_review_deadline_default",
            "ta_reviews_per_question",
        ]
        # the label indices should correspond to the field-names
        field_labels = [
            "Deadline for Student Reviews",
            "Deadline for TA Reviews",
            "Assign TA reviews per question",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[
            "ta_reviews_per_question"
        ].help_text = (
            "Whether to assign TA reviews per question or per the whole assignment:"
        )
        self.fields["student_review_deadline_default"].initial = timezone.now()
        self.fields["ta_review_deadline_default"].initial = timezone.now()

    def assign_rubric(self, rubric, question):
        question.rubric = rubric
        question.save()

    def get_question_rubric(self, question):
        return question.rubric

    def get_correct_temporal_order(self, data):
        assignment = self.assignment or self.instance.assignment

        if not assignment.submission_required:
            return []

        if assignment.deadline is None:
            raise forms.ValidationError(
                "The assignment itself does not have a deadline yet."
                + " Please configure the assignment first."
            )

        return [
            {"time": assignment.hard_deadline(), "reason": ""},
            # {'time': data['student_review_release_time_default'],
            #     'key': 'student_review_release_time_default',
            #     'reason': 'Student review release time should be after ' +
            #         'the actual deadline of the assignment, i.e: %s.' % assignment.deadline.strftime('%c')},
            {
                "time": data["student_review_deadline_default"],
                "key": "student_review_deadline_default",
                "reason": "Student review deadline should be after "
                + "the actual (hard) deadline of the assignment, i.e: %s."
                % assignment.hard_deadline().strftime("%c"),
            },
            # {'time': data['ta_review_release_time_default'],
            #     'key': 'ta_review_release_time_default',
            #     'reason': 'Release time for the TA reviews should be after the deadline for student reviews.'},
            {
                "time": data["ta_review_deadline_default"],
                "key": "ta_review_deadline_default",
                "reason": "Deadline for the TA reviews should be after the deadline for student reviews.",
            },
        ]


class ReviewContentForm(ChoicesForm):
    class Meta:
        model = ReviewAssignment
        fields = ["nopublicuse"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['timer'] = forms.FloatField(
            widget=forms.HiddenInput()
        )

    def get_components(self):
        "Component refers to the questions in the upper hand model: SubmissionComponent"
        if self.instance.question is not None:
            return self.instance.submission.components.filter(
                question=self.instance.question
            )
        return self.instance.submission.components.all()

    def get_rubric_questions(self, component):
        return component.question.rubric.questions.all().order_by('title')

    def get_choice(self, rubric_question, component):
        return self.instance.reviewcontent_set.filter(
            choice__question=rubric_question, submission_component=component
        ).first()

    def get_components_dict(self):
        return dict(
            [
                ((rc.submission_component.id, rc.choice.question.id), rc)
                for rc in self.instance.reviewcontent_set.all()
            ]
        )

    def make_choice(self, component):
        "Choice refers to the content: model that saved the choices made: ReviewContent"
        return ReviewContent(
            review_assignment=self.instance, submission_component=component
        )

    def clean(self):
        cleaned_data = super().clean()
        awr = self.instance.submission.get_review_settings()
        if awr is None:
            raise forms.ValidationError(
                "No review settings exist for this assignment, please contact staff."
            )
        if (
            self.instance.submission.calibration_id == 0
            and self.instance.grader.role == "student"
            and timezone.now() > awr.student_review_deadline_default
        ):
            raise forms.ValidationError("Deadline for reviews has passed.")

        return cleaned_data

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        self.instance.timer += self.cleaned_data['timer']
        self.instance.populate_grade()
        self.instance.save()
        
        sub = self.instance.submission
        sub.populate_grade()
        sub.save()


class RubricForm(ModelForm):
    questions = forms.ModelMultipleChoiceField(
        RubricQuestion._default_manager,
        required=False,
        help_text="Choose from the set of existing questions or create new ones:",
        widget=MultipleSelectWithPop(href="/review/rubric/question/create/?popup=1"),
    )
    # unfortunately couldn't use reverse here

    class Meta:
        model = Rubric
        fields = ["name", "questions"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": "form-control"})

        if self.instance.pk is not None:
            self.fields["questions"].initial = [
                q.id for q in self.instance.questions.all()
            ]


class RubricQuestionMultipleChoiceForm(ModelForm):
    class Meta:
        model = RubricQuestionMultipleChoiceItem
        fields = ["question", "text", "marks"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": "form-control"})


class RubricQuestionForm(ModelForm):
    class Meta:
        model = RubricQuestion
        fields = ["title", "text", "min_reason_length", "max_reason_length"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": "form-control"})

    # def clean_category(self):
    #     data = self.cleaned_data['category']
    #     if data == "NONE":
    #         raise forms.ValidationError('Please select a valid type for the rubric question before saving it.')
    #     return data


class ReviewAssignmentForm(ModelForm):
    "not used right now"
    deadline = forms.SplitDateTimeField(
        input_date_formats=["%Y-%m-%d"],
        input_time_formats=["%H:%M %p"],
        widget=forms.SplitDateTimeWidget(),
    )

    forms.DateInput.input_type = "date"
    forms.TimeInput.input_type = "time"

    class Meta:
        model = ReviewAssignment
        fields = ["submission", "grader"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": "form-control"})

    def save(self, commit=True):
        model = super(ReviewAssignmentForm, self).save(commit=False)
        model.deadline = self.cleaned_data["deadline"]
        if commit:
            model.save()
        return model


class AssignTAReviewsForm(AssignTAsForm):
    def get_max_num(self):
        return ReviewBase.submission_without_ta_review_count(self.assignment.id)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.reviews_per_question = (
            self.assignment.assignmentwithreviews.ta_reviews_per_question
        )
        if not self.reviews_per_question:
            self.fields["evaluate_student_reviews"] = forms.BooleanField(
                initial=True,
                help_text="If true, for each submission that is spot checked the same TA will also"
                + " evaluate the student reviews of that submission (makes evaluations more efficient).",
            )

    def evaluate_student_reviews(self):
        return (not self.reviews_per_question) and self.cleaned_data[
            "evaluate_student_reviews"
        ]


class AssignTAGradingForm(AssignTAReviewsForm):
    def evaluate_student_reviews(self):
        return False

    def add_fields(self):
        for question in self.assignment.questions.all():
            field_name = "tas_%d" % question.id
            self.fields[field_name] = forms.MultipleChoiceField(
                required=True,
                label=question.title + " TAs",
                choices=[
                    (cm.id, cm.display())
                    for cm in CourseBase.get_graders(self.assignment.course.id)
                ],
            )
            self.fields[field_name].widget.attrs.update({"data-toggle": "selectpicker"})

    def clean_tas_field(self):
        self.tas = []
        for question in self.assignment.questions.all():
            field_name = "tas_%d" % question.id
            self.tas.append(
                CourseMember._default_manager.filter(
                    id__in=self.cleaned_data[field_name]
                )
            )
            if self.tas[-1].count() == 0:
                raise forms.ValidationError(
                    "No valid TA was selected for question " + question.title
                )


class UploadTAGradingForm(forms.Form):
    file = forms.FileField()


class AssignStudentReviewsForm(forms.Form):
    """
    Form for assigning student reviews

    Parameters if `course.enable_independent_pool == False`:
      - num
    Otherwise:
      - num_independent
      - num_supervised

    :param assignment: The assignment object for which the reviews should be assigned
    :type assignment: peer_assignment.models.Assignment
    """

    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop("assignment")
        super().__init__(*args, **kwargs)

        subs = self.assignment.assignmentsubmission_set.filter(calibration_id=0)

        if self.assignment.course.enable_independent_pool:
            num_subs = {
                "independent": subs.filter(author__is_independent=True).count(),
                "supervised": subs.filter(author__is_independent=False).count(),
            }
        else:
            num_subs = {"": subs.count()}

        for stype, count in num_subs.items():
            self.fields["num" + ("_" if stype else "") + stype] = forms.IntegerField(
                initial=max(0, min(3, count - 1)),
                min_value=0,
                max_value=max(0, count - 1),
                help_text=(
                    "Number of reviews per"
                    + (" " if stype else "")
                    + stype
                    + " submission to assign:"
                ),
            )

class UploadStudentReviewsForm(forms.Form):
    file = forms.FileField()

class UploadSpotcheckingPriorityForm(forms.Form):
    file = forms.FileField()