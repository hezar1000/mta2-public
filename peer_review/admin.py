from django.contrib import admin
from nested_admin import NestedStackedInline, NestedModelAdmin, NestedTabularInline
from .models import *

# Register your models here.


class AssignmentWithReviewsAdmin(admin.ModelAdmin):
    pass


admin.site.register(AssignmentWithReviews, AssignmentWithReviewsAdmin)


class RubricAdmin(admin.ModelAdmin):
    pass


admin.site.register(Rubric, RubricAdmin)


class RubricQuestionAdmin(admin.ModelAdmin):
    pass


admin.site.register(RubricQuestion, RubricQuestionAdmin)


class RubricQuestionMultipleChoiceItemAdmin(admin.ModelAdmin):
    pass


admin.site.register(
    RubricQuestionMultipleChoiceItem, RubricQuestionMultipleChoiceItemAdmin
)


class ReviewContentInline(NestedStackedInline):
    model = ReviewContent
    min_num = 0
    extra = 0
    raw_id_fields = ["submission_component"]


class ReviewAssignmentAdmin(NestedModelAdmin):
    inlines = [ReviewContentInline]
    list_display = (
        "submission",
        "grader",
        "submitted",
        "is_groundtruth",
        "nopublicuse",
    )
    list_filter = ("submitted", "is_groundtruth", "nopublicuse")
    raw_id_fields = ["submission", "question"]


admin.site.register(ReviewAssignment, ReviewAssignmentAdmin)


class ReviewContentAdmin(admin.ModelAdmin):
    pass


admin.site.register(ReviewContent, ReviewContentAdmin)


class ReviewContentFileAdmin(admin.ModelAdmin):
    pass


admin.site.register(ReviewContentFile, ReviewContentFileAdmin)


class ValidationRuleAdmin(admin.ModelAdmin):
    pass


admin.site.register(ValidationRule, ValidationRuleAdmin)
