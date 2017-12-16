from __future__ import unicode_literals

import logging

from datetime import timedelta

from django.utils.timezone import now
from django.core.management.base import BaseCommand

from ats_sms_operator.config import ATS_STATES, get_output_sms_model
from ats_sms_operator.config import settings
from ats_sms_operator.sender import DeliveryRequest, send_and_update_sms_states


LOGGER = logging.getLogger('ats_sms')


class Command(BaseCommand):

    def handle(self, *args, **options):
        OutputSMSModel = get_output_sms_model()
        to_check = OutputSMSModel.objects.filter(
            state__in=(ATS_STATES.OK, ATS_STATES.NOT_SENT, ATS_STATES.SENT))
        if to_check.exists():
            send_and_update_sms_states(*[DeliveryRequest(sms) for sms in to_check])

        idle_output_sms = OutputSMSModel.objects.filter(
            state=ATS_STATES.OK, created_at__lt=now() + timedelta(minutes=settings.IDLE_MESSAGES_TIMEOUT_MINUTES)
        )
        if settings.LOG_IDLE_MESSAGES and idle_output_sms.exists():
            LOGGER.warning('{count_sms} Output SMS is more than {timeout} minutes in state "OK"'.format(
                count_sms=idle_output_sms.count(), timeout=settings.IDLE_MESSAGES_TIMEOUT_MINUTES
            ))
