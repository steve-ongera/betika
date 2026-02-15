from django.core.management.base import BaseCommand
from aviator.game_engine import AviatorGameEngine

class Command(BaseCommand):
    help = 'Run the Aviator game engine'

    def handle(self, *args, **options):
        engine = AviatorGameEngine()
        self.stdout.write(self.style.SUCCESS('Starting Aviator Game Engine...'))
        engine.run()