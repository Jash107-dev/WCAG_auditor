import json
import os
from django.core.management.base import BaseCommand
from core.models import Rule

class Command(BaseCommand):
    help = 'Load WCAG rules from JSON file'

    def handle(self, *args, **kwargs):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        file_path = os.path.join(base_dir, 'data', 'wcag_rules.json')

        with open(file_path) as f:
            rules = json.load(f)

        for rule in rules:
            Rule.objects.get_or_create(
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

        self.stdout.write(self.style.SUCCESS('WCAG rules loaded successfully!'))
