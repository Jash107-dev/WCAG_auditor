from django.db import models


class Project(models.Model):
    domain = models.URLField()
    wcag_level = models.CharField(max_length=10)
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.domain


class Page(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    url = models.URLField()
    html_snapshot = models.TextField()
    status = models.CharField(max_length=20, default="pending")

    def __str__(self):
        return self.url


class Rule(models.Model):
    wcag_id = models.CharField(max_length=20)
    title = models.CharField(max_length=100)
    level = models.CharField(max_length=10)
    category = models.CharField(max_length=50)
    check_type = models.CharField(max_length=20)
    description = models.TextField()
    logic = models.TextField()
    fix_suggestion = models.TextField()

    def __str__(self):
        return self.wcag_id


class Issue(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE)
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE)
    severity = models.CharField(max_length=20)
    message = models.TextField()
    fix = models.TextField()

    def __str__(self):
        return self.message
