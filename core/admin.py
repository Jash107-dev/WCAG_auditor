from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import Project, Page, Rule, Issue

admin.site.register(Project)
admin.site.register(Page)
admin.site.register(Rule)
admin.site.register(Issue)