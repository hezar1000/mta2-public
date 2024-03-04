from django.contrib import admin

from .models import EvaluationAssignment, EvaluationContent, EvaluationSettings

admin.site.register(EvaluationAssignment)
admin.site.register(EvaluationContent)
admin.site.register(EvaluationSettings)
