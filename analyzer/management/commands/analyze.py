from django.core.management.base import BaseCommand
from analyzer.engine import analyze_project
from core.models import Project

class Command(BaseCommand):
    help = 'Run WCAG analysis on a given project ID'

    def add_arguments(self, parser):
        parser.add_argument('project_id', type=int, help='The ID of the project to analyze')
        parser.add_argument('--async', action='store_true', dest='async_mode', help='Run analysis asynchronously using Celery')

    def handle(self, *args, **kwargs):
        project_id = kwargs['project_id']
        async_mode = kwargs['async_mode']

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Project with ID {project_id} does not exist.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Starting analysis for Project: {project.domain}'))

        analyze_project(project_id, async_mode=async_mode)

        project.status = 'analyzed'
        project.save()

        self.stdout.write(self.style.SUCCESS(f'Successfully completed analysis for project {project_id}'))
