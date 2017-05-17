from __future__ import unicode_literals

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ats_sms_operator.config import ATS_STATES, get_output_sms_model, settings


class Command(BaseCommand):

    def handle(self, *args, **options):
        get_output_sms_model().objects.filter(
            state=ATS_STATES.PROCESSING, changed_at__lt=timezone.now() - timedelta(seconds=settings.PROCESSING_TIMEOUT)
        ).update(state=ATS_STATES.TIMEOUT)
