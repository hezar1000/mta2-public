from django import forms
from django.forms import DateTimeField
from django.contrib.admin import widgets
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from django.utils import timezone

import re, datetime

from .models import Appeal, InaptReport, InaptFlag
from peer_course.base import CourseBase
from peer_home.forms import ModelFormControl


class AppealForm(ModelFormControl):
    class Meta:
        model = Appeal
        fields = ["assignee", "status", "response"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].choices = [
            (g.id, g.display())
            for g in CourseBase.get_course_staff(
                self.instance.submission.assignment.course.id
            )
        ]

    # def disable_fields(self, is_staff):
    #     if is_staff:
    #         self.fields['request'].disabled = True
    #     else:
    #         for field_name in self.fields:
    #             if field_name != 'request':
    #                 self.fields[field_name].disabled = True

    # def save(self, commit=True):
    #    model = super(AppealForm, self).save(commit=False)

    #    print("qs ", model.request)
    # model.status
    #    if commit:
    #        model.save()
    # print("rs ", model.submission)
    #    return model


class InaptReportForm(ModelFormControl):
    class Meta:
        model = InaptReport
        fields = ["reason", "assignee", "reporter", "review"]
        widgets = {
            "assignee": forms.HiddenInput(),
            "reporter": forms.HiddenInput(),
            "review": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        if "initial" in kwargs and "review" in kwargs["initial"]:
            kwargs["initial"]["assignee"] = (
                CourseBase.get_tas(
                    kwargs["initial"]["review"].submission.assignment.course.id
                )
                .order_by("?")
                .first()
            )
        super().__init__(*args, **kwargs)

        self.fields["reason"].label = "Please describe why this review is inappropriate"
        self.fields["reason"].help_text = "Rude, Unfair, etc."


class InaptFlagForm(ModelFormControl):
    class Meta:
        model = InaptFlag
        fields = ["reason", "reporter", "review"]
        widgets = {"reporter": forms.HiddenInput(), "review": forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["reason"].label = "Please describe why this review is inappropriate"
        self.fields["reason"].help_text = "Rude, Unfair, etc."



class ImportStudentGrades(forms.Form):
    file = forms.FileField()


class UploadComponentGrades(forms.Form):
    file = forms.FileField()


class UploadGradingItems(forms.Form):
    file = forms.FileField()

