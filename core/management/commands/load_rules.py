import json
import os
from django.core.management.base import BaseCommand
from core.models import Rule


class Command(BaseCommand):
    help = 'Load WCAG rules from JSON file'

    def handle(self, *args, **kwargs):
        commands_folder = os.path.abspath(__file__)
        management_folder = os.path.dirname(commands_folder)
        management_parent = os.path.dirname(management_folder)
        core_folder = os.path.dirname(management_parent)
        project_folder = os.path.dirname(core_folder)

        file_path = os.path.join(project_folder, 'data', 'wcag_rules.json')

        f = open(file_path)
        rules_data = json.load(f)
        f.close()

        for rule in rules_data:
            Rule.objects.update_or_create(
                wcag_id=rule['wcag_id'],
                defaults={
                    'title': rule['title'],
                    'level': rule['level'],
                    'category': rule['category'],
                    'check_type': rule['check_type'],
                    'description': rule['description'],
                    'logic': rule['logic'],
                    'fix_suggestion': rule['fix_suggestion'],
                }
            )

        self.stdout.write(self.style.SUCCESS('rules loaded succesfully!'))
