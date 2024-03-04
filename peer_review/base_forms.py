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
from peer_assignment.models import SubmissionComponent
from peer_home.popup_widgets import SelectWithPop, MultipleSelectWithPop

from peer_course.base import CourseBase
from peer_course.models import CourseMember

import re, datetime


class AssignmentSettingsForm(forms.ModelForm):

    # class Meta:
    #     model = AssignmentWithReviews
    #     fields = ['student_review_deadline_default', 'ta_review_deadline_default']

    def __init__(self, *args, **kwargs):
        self.assignment = None
        self.awr = None
        if "assignment" in kwargs:
            self.assignment = kwargs.pop("assignment")
        elif "awr" in kwargs:
            self.awr = kwargs.pop("awr")
            if self.awr is None:
                raise ValueError("Provided `awr` argument is empty (None).")
            self.assignment = self.awr.assignment
        super().__init__(*args, **kwargs)

        if self.assignment is None:
            if self.instance is None:
                raise ValueError(
                    "%s must be provided to %s if instance is not None"
                    % (self.Meta.fk_name, self.Meta.model.__name__ + "Form")
                )
            if hasattr(self.instance, "assignment"):
                self.assignment = self.instance.assignment
            if hasattr(self.instance, "awr"):
                self.awr = self.instance.awr
                self.assignment = self.awr.assignment

        rubric_choices = [(r.id, r.name) for r in Rubric._default_manager.all()]

        for i, question in enumerate(self.assignment.questions.all()):
            chosen = self.get_question_rubric(question)
            self.fields["rubric_%s" % question.id] = forms.ChoiceField(
                label="Rubric for question %d [%s]" % (i + 1, question.title),
                initial=chosen.id if chosen is not None else None,
                choices=rubric_choices,
                required=True,
                help_text="Choose an existing rubric or create a new one:",
                widget=SelectWithPop(reverse("review:rubric_create") + "?popup=1"),
            )

        for i, field in enumerate(self.Meta.fields):
            if "deadline" in field:
                self.fields[field] = forms.SplitDateTimeField(
                    label=self.Meta.field_labels[i],
                    input_date_formats=["%Y-%m-%d"],
                    input_time_formats=["%H:%M:%S", "%H:%M"],
                    widget=forms.SplitDateTimeWidget(),
                )

        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": "form-control"})

    def clean(self):
        cleaned_data = super().clean()

        temp_order = self.get_correct_temporal_order(cleaned_data)

        errors = []
        for i in range(len(temp_order) - 1):
            if temp_order[i]["time"] > temp_order[i + 1]["time"]:
                errors.append(
                    [
                        temp_order[i + 1]["key"],
                        forms.ValidationError(_(temp_order[i + 1]["reason"])),
                    ]
                )
        # print(dict(errors))
        if errors:
            # print(dict(errors))
            raise forms.ValidationError(dict(errors))

        return cleaned_data

    def save(self, commit=True):
        super().save(commit)

        # print('we already have:', self.instance.assignment)
        if self.awr:
            self.instance.awr = self.awr
            self.instance.save()
        elif self.assignment:
            self.instance.assignment = self.assignment
            self.instance.save()

        for i, question in enumerate(self.assignment.questions.all()):
            field_name = "rubric_%s" % question.id
            if field_name in self.cleaned_data:
                r = Rubric._default_manager.filter(
                    id=self.cleaned_data[field_name]
                ).first()
                if r is not None:
                    self.assign_rubric(r, question)

        return self.instance


class ChoicesForm(forms.ModelForm):
    # class Meta:
    #     model = ReviewAssignment
    #     fields = ['nopublicuse']

    def get_components(self):
        "Component refers to the questions in the upper hand model"
        raise NotImplementedError

    def get_rubric_questions(self, component):
        raise NotImplementedError

    def get_choice(self, rubric_question, component):
        raise NotImplementedError

    def get_components_dict(self):
        raise NotImplementedError

    def make_choice(self, component):
        "Choice refers to the content: model that saved the choices made"
        raise NotImplementedError

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for component in self.get_components():
            for rubric_question in self.get_rubric_questions(component):
                chosen = self.get_choice(rubric_question, component)

                choice_items = [
                    (str(choice.id), choice.text)
                    for choice in rubric_question.choices.all()
                ]

                choice_field_name = "rq_%d_mc_%d" % (component.id, rubric_question.id)
                reason_field_name = "rq_%d_reason_%d" % (
                    component.id,
                    rubric_question.id,
                )
                self.fields[choice_field_name] = forms.ChoiceField(
                    label=rubric_question.text,
                    initial=chosen.choice.id if chosen is not None else None,
                    choices=choice_items,
                    widget=forms.RadioSelect(attrs={"id": choice_field_name}),
                )
                if rubric_question.min_reason_length == 0:
                    self.fields[reason_field_name] = forms.CharField(
                        # TODO: I'm not sure if the ordering is always gonna be correct or not
                        # TODO: might need to change the label
                        max_length=rubric_question.max_reason_length,
                        label="Please briefly describe your reasoning",
                        initial=chosen.reason if chosen is not None else None,
                        widget=forms.Textarea(attrs={"rows": 3}),
                    )
                    self.fields[reason_field_name].required = False
                else:
                    self.fields[reason_field_name] = forms.CharField(
                        # TODO: I'm not sure if the ordering is always gonna be correct or not
                        # TODO: might need to change the label
                        min_length=rubric_question.min_reason_length,
                        max_length=rubric_question.max_reason_length,
                        label="Please briefly describe your reasoning",
                        initial=chosen.reason if chosen is not None else None,
                        widget=forms.Textarea(attrs={"rows": 3}),
                    )

    # TODO: add atomic decorators
    def save(self, commit=True):
        m = super().save(commit=False)

        has_file = False
        components = self.get_components_dict()

        for field_name in self.cleaned_data:

            # TODO: fix regex
            if field_name.startswith("rq"):
                found = re.search("rq_([0-9]+)_([a-z]+)_([0-9]+)", field_name)
                component_id = int(found.group(1))
                field_type = found.group(2)
                rq_id = int(found.group(3))
                # if rq_type == 'file':
                #     has_file = True
            elif field_name.startswith("nopublicuse"):
                self.instance.nopublicuse = self.cleaned_data[field_name]
                continue
            elif field_name.startswith('timer'):
                continue
            else:
                print("mismatch", field_name)

            component = self.get_components().get(pk=component_id)

            # TODO: validate if question and sc exist

            if not (component_id, rq_id) in components:
                components[component_id, rq_id] = self.make_choice(component)

            component = components[component_id, rq_id]
            if field_type == "mc":
                component.choice_id = self.cleaned_data[field_name]
            elif field_type == "reason":
                component.reason = self.cleaned_data[field_name]

            # print("updated: ", field_type, " to ", self.cleaned_data[field_name])

        for component in components.values():
            component.save()

        self.instance.submitted = True
        self.instance.submission_date= timezone.now()
        self.instance.save()

        return has_file


class AssignTAsForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop("assignment")
        super().__init__(*args, **kwargs)

        max_num = self.get_max_num()
        self.fields["num_to_assign"] = forms.IntegerField(
            required=True, min_value=0, initial=max_num, max_value=max_num
        )

        self.add_fields()

    def add_fields(self):
        self.fields["tas"] = forms.MultipleChoiceField(
            required=True,
            label="TAs",
            choices=[
                (cm.id, cm.display())
                for cm in CourseBase.get_graders(self.assignment.course.id)
            ],
        )
        self.fields["tas"].widget.attrs.update({"data-toggle": "selectpicker"})

    def clean_tas_field(self):
        self.tas = CourseBase.get_graders(self.assignment.course.id).filter(
            id__in=self.cleaned_data["tas"]
        )
        if self.tas.count() == 0:
            raise forms.ValidationError("No valid TA was selected")

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)
        self.clean_tas_field()

    def get_all_tas(self):
        return self.tas
