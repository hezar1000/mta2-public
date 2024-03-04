from django.contrib import admin

# Register your models here.

from .models import *

# Register your models here.


@admin.register(Appeal)
class AppealAdmin(admin.ModelAdmin):
    pass


@admin.register(InaptReport)
class InaptReportAdmin(admin.ModelAdmin):
    pass


@admin.register(InaptFlag)
class InaptFlagAdmin(admin.ModelAdmin):
    pass


@admin.register(GradingItem)
class GradingItem(admin.ModelAdmin):
    pass