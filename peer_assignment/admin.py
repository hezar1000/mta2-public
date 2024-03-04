from django.contrib import admin
from nested_admin import NestedStackedInline, NestedModelAdmin, NestedTabularInline
from .models import *

# Register your models here.


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    pass


# class AssignmentFileAdmin(admin.ModelAdmin):
# 	pass
# admin.site.register(AssignmentFile, AssignmentFileAdmin)


class SubmissionComponentInline(NestedStackedInline):
    model = SubmissionComponent
    min_num = 0
    extra = 0
    raw_id_fields = ["question"]
    exclude = ("manual_grade", "ta_review_grade", "automatic_grade")


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(NestedModelAdmin):
    model = AssignmentSubmission
    inlines = [SubmissionComponentInline]
    list_display = (
        "assignment",
        "author",
        "calibration_id",
        "nopublicuse",
        "time_submitted",
        "time_last_modified",
        "late_units_used",
        "attempts",
    )
    search_fields = (
        "assignment__name",
        "author__user__first_name",
        "author__user__last_name",
    )
    date_hierarchy = "time_submitted"
    list_filter = ("nopublicuse", "assignment__course", "attempts")


@admin.register(AssignmentQuestion)
class AssignmentQuestionAdmin(admin.ModelAdmin):
    search_fields = ("description", "title", "assignment__name")


@admin.register(AssignmentQuestionMultipleChoice)
class AssignmentQuestionMultipleChoiceAdmin(admin.ModelAdmin):
    pass


@admin.register(SubmissionComponent)
class SubmissionComponentAdmin(admin.ModelAdmin):
    search_fields = (
        "submission__assignment__name",
        "submission__author__user__first_name",
        "submission__author__user__last_name",
    )
