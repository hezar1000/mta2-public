from django import forms
from django.conf import settings
from django.forms import ModelForm, DateTimeField
from django.contrib.admin import widgets
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from django.db import transaction
from django.core.files import File
from django.utils import timezone
import re, datetime, math
from zipfile import ZipFile
from .models import (
    Assignment,
    AssignmentQuestion,
    AssignmentSubmission,
    AssignmentQuestionMultipleChoice,
    SubmissionComponent,
)
from peer_course.models import CourseMember
from peer_review.choices import MULTIPLECHOICE, TEXT, FILE
from peer_assignment.templatetags.code_parse import code_parse


class AssignmentForm(ModelForm):

    deadline = forms.SplitDateTimeField(
        widget=forms.SplitDateTimeWidget(date_format="%Y-%m-%d", time_format="%I:%M:%S")
    )

    release_time = forms.SplitDateTimeField(
        widget=forms.SplitDateTimeWidget(date_format="%Y-%m-%d", time_format="%I:%M:%S")
    )

    forms.DateInput.input_type = "date"
    forms.TimeInput.input_type = "time"

    class Meta:
        model = Assignment
        fields = ["name", "browsable", "deadline", "release_time"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": "form-control"})
        # self.fields['deadline'] = forms.SplitDateTimeField(
        #    input_date_formats=['%Y-%m-%d'],
        # input_date_formats=['%m/%d/%Y'],
        #        input_time_formats=['%H:%M %p'],
        #    widget=forms.SplitDateTimeWidget())

    def save(self, commit=True):
        model = super(AssignmentForm, self).save(commit=False)

        model.deadline = self.cleaned_data["deadline"]
        # print("qs ", self.cleaned_data["questions"])
        if commit:
            model.save()
        # print("rs ", model.questions)
        return model


#    def clean_deadline(self) :
#        if datetime.date() > self.deadline :
#            raise ValidationError(_('The deadline has passed.'))


# from django.forms.widgets import Widget
# from django.template import Template, Context
# from django.template import loader
# from django.utils.safestring import mark_safe


# class MyFileWidget(Widget):
#     template = '''{% load upload_field %}
#     <div style="max-width: 600px; padding: 0 10px 0 10px">
#     {% upload_field name file label %}
#     </div>'''

#     def render(self, name, file=None, attrs=None):
#         return mark_safe(
#             Template(MyFileWidget.template).render(Context({
#                 'name': name,
#                 'file': file,
#         })))
#         # return mark_safe(MyFileWidget.template.format(name=name, label=label, file=file))


class SubmissionComponentForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ["nopublicuse"]

    def __init__(self, *args, **kwargs):
        self.assignment = assignment = kwargs.pop("assignment")
        self.author = None
        if "author" in kwargs:
            self.author = kwargs.pop("author")
        self.enforce_deadline = kwargs.pop("enforce_deadline", True)

        self.warns = []

        super(SubmissionComponentForm, self).__init__(*args, **kwargs)

        for question in assignment.questions.all():

            chosen_exists = question.submissioncomponent_set.filter(
                submission__id=self.instance.id
            ).exists()
            if chosen_exists:
                chosen = question.submissioncomponent_set.get(
                    submission__pk=self.instance.id
                )
            else:
                chosen = None

            if question.category == MULTIPLECHOICE:

                choice_items = list()
                for choice in question.choices.all():
                    choice_items.append((str(choice.id), choice.choice_text))

                field_name = "rq_mc_%s" % question.id
                # TODO: change to ModelMultipleChoiceField?
                # https://docs.djangoproject.com/en/2.0/ref/forms/fields/
                self.fields[field_name] = forms.ChoiceField(
                    label=question.description,
                    initial=chosen.content if chosen is not None else None,
                    choices=choice_items,
                    widget=forms.RadioSelect(attrs={"id": "rq_mc_%s" % question.id}),
                )

            elif question.category == TEXT:

                # gather validations for the field

                validator_list = []
                # TODO: add the validation rules
                """
                validation_rules = question.validationrule_set.all()
                for rule in validation_rules:
                    if rule.rule_type == MIN_CHAR:
                        length = int(rule.rule_content)
                        msg = "Your answer for the question '%s' is not valid.  It needs to have AT LEAST %s characters." % (question.text, length)
                        validator_list.append(validators.MinLengthValidator(length, msg))
                    elif rule.rule_type == MAX_CHAR:
                        length = int(rule.rule_content)
                        msg = "Your answer for the question '%s' is not valid.  It needs to have AT MOST %s characters." % (question.text, length)
                        validator_list.append(validators.MaxLengthValidator(length, msg))
                """
                field_name = "rq_text_%s" % question.id
                # print(self.author)
                if question.assignment.id == 86 or question.assignment.id == 105 or question.assignment.id == 106 or question.assignment.id == 144 or question.assignment.id == 254:
                    max_l= 5000
                else:
                    max_l= 2500
                author = self.author or self.instance.author
                self.fields[field_name] = forms.CharField(
                    label=code_parse(question.description, author=author),
                    max_length=max_l,
                    widget=forms.Textarea(
                        attrs={"id": "rq_text_%s" % question.id, "cols": 100}
                    ),
                    validators=validator_list,
                )
                if chosen is not None:
                    self.fields[field_name].initial = chosen.content

            elif question.category == FILE:

                field_name = "rq_file_%s" % question.id
                self.fields[field_name] = forms.FileField(
                    label=question.description,
                    required=not chosen_exists,
                    widget=forms.FileInput(
                        attrs={"id": "rq_file_%s" % question.id, "multiple": "multiple"}
                    ),
                    # widget=MyFileWidget(attrs={
                    #     'name': 'rq_file_%s' % question.id,
                    # })
                )

                if chosen_exists:
                    #    file_links = ReviewUtils.get_file_links(
                    #        question, self.instance)
                    self.fields[field_name].help_text = "file_links"
                    self.fields[field_name].initial = chosen.attachment
        # print(self.fields)

    #    def clean_deadline(self) :
    #        if datetime.date() > self.instance.deadline :
    #            raise ValidationError(_('The deadline has passed.'))
    def clean(self):
        cleaned_data = super(SubmissionComponentForm, self).clean()
        self.instance.assignment = self.assignment
        if self.author:
            self.instance.author = self.author
        if not self.instance.can_compose_submission() and self.enforce_deadline:
            raise ValidationError(
                "You cannot create/modify a submission anymore because the deadline has passed."
            )
        return cleaned_data

    def inspect_attachment(self, attachment, question):
        if attachment is not None:
            ext = attachment.name.split(".")[-1]
            if ext not in settings.LANGUAGE_EXT_TO_NAME and ext != "pdf":
                self.warns.append(
                    "Uploaded file for question %s (%s) is not supported, you probably want to fix this."
                    % (question.title, attachment.name)
                )

    def save(self, commit=True):
        m = super(SubmissionComponentForm, self).save(commit=False)
        self.instance.assignment = self.assignment
        if self.author:
            self.instance.author = self.author
        if self.enforce_deadline:
            self.instance.late_units_used = (
                self.instance.assignment.calculate_late_units_now()
            )
        self.instance.save()

        has_file = False

        # Is this an initial commit? (so save instead of update)
        initial = not SubmissionComponent._default_manager.filter(
            submission=self.instance
        ).exists()

        for field_name in self.cleaned_data:

            content = self.cleaned_data[field_name]
            attachment = None

            if field_name.startswith("rq_mc"):
                found = re.search("rq_mc_([0-9]+)", field_name)
                rq_id = found.group(1)
            elif field_name.startswith("rq_text"):
                found = re.search("rq_text_([0-9]+)", field_name)
                rq_id = found.group(1)
            elif field_name.startswith("rq_file"):
                found = re.search("rq_file_([0-9]+)", field_name)
                rq_id = found.group(1)
                attachment = content
                content = ""
                has_file = True
            elif field_name.startswith("nopublicuse"):
                self.instance.nopublicuse = self.cleaned_data[field_name]
                self.instance.save()
                continue
            else:
                print("mismatch", field_name)
                raise Exception("mismatch in SubmissionComponent form")

            question = AssignmentQuestion._default_manager.get(pk=rq_id)

            if field_name in self.changed_data:
                self.inspect_attachment(attachment, question)
            # TODO: maybe handle rubric questions too?

            # print('-------DEBUGGING INFO-------')
            # count = SubmissionComponent._default_manager.filter(
            #     submission=self.instance,
            #     question=question,
            # ).count()
            # if count == 1 :
            #     print('exists ', SubmissionComponent._default_manager.get(
            #         submission=self.instance,
            #         question=question,
            #     ))
            # print('raid:', self.instance.id, ' rqid:', rq_id)
            # print('-------END OF DB INFO-------')

            if initial:
                SubmissionComponent(
                    submission=self.instance,
                    question=question,
                    content=content,
                    attachment=attachment,
                ).save()
            else:
                for sc in SubmissionComponent._default_manager.filter(
                    question=question, submission=self.instance
                ):
                    sc.content = content
                    sc.attachment = attachment
                    sc.save()
                # print('updated: ', content, attachment)

        return self.instance


class AssignmentQuestionForm(ModelForm):
    class Meta:
        model = AssignmentQuestion
        fields = ["category", "title", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": "form-control"})

    def clean_category(self):
        data = self.cleaned_data["category"]
        if data == "NONE":
            raise forms.ValidationError(
                "Please select a valid type for the rubric question before saving it."
            )
        return data


class AssignmentQuestionMultipleChoiceForm(ModelForm):
    class Meta:
        model = AssignmentQuestionMultipleChoice
        fields = ["question", "choice_text", "marks"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": "form-control"})


class BatchSubmitForm(forms.Form):
    submission_zip = forms.FileField(
        label="Submission Zip File",
        help_text='The file names should follow the format of "<username>.zip"'
        + 'which contains "<q#>.pdf/txt" files',
    )

    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop("assignment")
        super().__init__(*args, **kwargs)

    def get_filename(self):
        return self.zipfile.name

    def clean(self):
        super().clean()

        self.components = {}

        self.zipfile = self.files["submission_zip"]

        name_ext = self.zipfile.name.split(".")
        username, ext = ".".join(name_ext[:-1]), name_ext[-1]

        if ext != "zip":
            raise ValidationError(
                'Only ".zip" files allowed: got file with the name "%s"'
                % self.zipfile.name
            )

        self.cm = CourseMember._default_manager.filter(
            user__username=username, course__id=self.assignment.course.id
        ).first()

        if self.cm is None:
            raise ValidationError(
                'Could not find course member with the username "%s"' % username
                + ' (the zip file should be named using the convention: "<username>.zip")'
            )

        with ZipFile(self.zipfile) as dezip_file:
            filenames = dezip_file.namelist()

            for filename in filenames:
                qn_ext = filename.split(".")
                qn, ext = qn_ext[0].split("_")[-1], qn_ext[-1]

                if ext != "pdf" and ext != "txt":
                    raise ValidationError(
                        'Only ".pdf" and ".txt" files are allowed: got file with the name "%s"'
                        % filename
                    )

                try:
                    qn = int(qn)
                except:
                    raise ValidationError(
                        "The question number must be a number. Instead found file '%s'"
                        % filename
                    )

                self.components[qn] = filename

        num_questions = self.assignment.questions.count()

        if len(self.components) != num_questions or set(self.components.keys()) != set(
            range(1, num_questions + 1)
        ):
            raise ValidationError(
                "All users should have submissions for questions 1..%d:" % num_questions
                + " got user %s with the list of questions %s"
                % (self.cm.user.username, str(list(self.components.keys())))
            )

        return self.cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        sub = AssignmentSubmission._default_manager.create(
            assignment=self.assignment, author=self.cm, nopublicuse=False
        )

        with ZipFile(self.zipfile) as dezip_file:
            filenames = dezip_file.namelist()
            for i, q in enumerate(self.assignment.questions.all()):
                with dezip_file.open(self.components[i + 1]) as f:
                    sub.components.create(question=q, content="", attachment=File(f))

        return sub
