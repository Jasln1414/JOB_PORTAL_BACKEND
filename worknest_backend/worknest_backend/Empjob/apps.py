from django.apps import AppConfig


class EmpjobConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Empjob'

    def ready(self):
        import Empjob.signals
