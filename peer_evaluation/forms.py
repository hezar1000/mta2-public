from django import forms
from django.core import validators
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from django.utils import timezone

from .models import EvaluationSettings, EvaluationContent, EvaluationAssignment
from .base import EvaluationBase
from peer_review.models import AssignmentWithReviews

from peer_review.base_forms import AssignmentSettingsForm, ChoicesForm, AssignTAsForm

import re, datetime


class EvaluationSettingsForm(AssignmentSettingsForm):
    class Meta:
        model = EvaluationSettings
        fk_name = "AssignmentWithReviewsForm"
        fields = ["student_evaluation_deadline_default"]
        # the label indices should correspond to the field-names
        field_labels = ["Deadline for Student Evaluations"]

    def assign_rubric(self, rubric, question):
        question.evaluation_rubric = rubric
        question.save()

    def get_question_rubric(self, question):
        return question.evaluation_rubric

    def get_correct_temporal_order(self, data):
        # assignment = self.assignment or self.instance.assignment
        awr = self.awr or self.instance.awr

        if awr.student_review_deadline_default is None:
            raise forms.ValidationError(
                "The deadline for student reviews has not been set yet."
                + " Please configure the review settings first."
            )

        return [
            # TODO use hard-deadline: do we allow grace days for reviews too?
            {"time": awr.student_review_deadline_default, "reason": ""},
            {
                "time": data["student_evaluation_deadline_default"],
                "key": "student_evaluation_deadline_default",
                "reason": "Student evaluation deadline should be after "
                + "the deadline of the student reviews, i.e: %s."
                % awr.student_review_deadline_default.strftime("%c"),
            },
        ]


class EvaluationContentForm(ChoicesForm):
    class Meta:
        model = EvaluationAssignment
        fields = ["nopublicuse"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['timer'] = forms.FloatField(
            widget=forms.HiddenInput()
        )

    def get_components(self):
        "component refers to the questions in the upper hand model: SubmissionComponent"
        return self.instance.review.submission.components.all()

    def get_rubric_questions(self, component):
        return component.question.evaluation_rubric.questions.all()

    def get_choice(self, rubric_question, component):
        return self.instance.contents.filter(
            choice__question=rubric_question, submission_component=component
        ).first()

    def get_components_dict(self):
        return dict(
            [
                ((rc.submission_component.id, rc.choice.question.id), rc)
                for rc in self.instance.contents.all()
            ]
        )

    def make_choice(self, component):
        "Choice refers to the content: model that saved the choices made: EvaluationContent"
        return EvaluationContent(
            evaluation=self.instance, submission_component=component
        )

    def clean(self):
        cleaned_data = super().clean()

        try:
            eval_settings = (
                self.instance.review.submission.assignment.assignmentwithreviews.evaluationsettings
            )
            if eval_settings is None:
                raise EvaluationSettings.DoesNotExist()
        except AssignmentWithReviews.DoesNotExist:
            raise forms.ValidationError(
                "No review setting exists for this assignment, please contact staff."
            )
        except EvaluationSettings.DoesNotExist:
            raise forms.ValidationError(
                "No review-evaluation setting exists for this assignment, please contact staff."
            )

        if (
            self.instance.grader.role == "student"
            and timezone.now() > eval_settings.student_evaluation_deadline_default
        ):
            raise forms.ValidationError("Deadline for review evaluations has passed.")

        return cleaned_data

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        self.instance.timer += self.cleaned_data['timer']
        self.instance.save()

class AssignTAEvaluationsForm(AssignTAsForm):
    def get_max_num(self):
        return EvaluationBase.review_without_ta_evaluation_count(self.assignment.id)
