import json
from django.core.management.base import BaseCommand
from core.models import Rule

class Command(BaseCommand):
    help = 'Load WCAG rules from JSON file'

    def handle(self, *args, **kwargs):
        with open('data/wcag_rules.json') as f:
            rules = json.load(f)

        for rule in rules:
            Rule.objects.get_or_create(
                wcag_id=rule['wcag_id'],
                level=rule['level'],
                description=rule['description'],
                logic=rule['logic']
            )

        self.stdout.write(self.style.SUCCESS('WCAG rules loaded successfully!'))