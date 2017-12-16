from __future__ import unicode_literals

import logging
from itertools import chain

from bs4 import BeautifulSoup

from django.db import models
from django.template import Context, Template
from django.utils import timezone
from django.utils.encoding import force_text
from django.utils.translation import ugettext

from chamber.shortcuts import get_object_or_none, change_and_save, bulk_change_and_save

from ats_sms_operator import logged_requests as requests
from ats_sms_operator.config import (settings, ATS_STATES, get_sms_template_model, get_output_sms_model,
                                     get_sms_template_model)


LOGGER = logging.getLogger('ats_sms')

header = """<?xml version="1.0" encoding="UTF-8" ?>
            <messages>
                <auth>
                    <name>{username}</name>
                    <password>{password}</password>
                </auth>"""
footer = '</messages>'


class DeliveryRequest(object):
    """
    Helper class to create ATS delivery requests from an output SMS. Since the output SMS itself must implement
    serialize_ats() method as well.
    """

    def __init__(self, output_sms):
        self.output_sms = output_sms

    def serialize_ats(self):
        return """<dlr uniq="{prefix}{pk}">{prefix}{pk}</dlr>""".format(
            pk=self.output_sms.pk, prefix=settings.UNIQ_PREFIX)


class ATSSMSException(Exception):
    pass


class SMSSendingError(ATSSMSException):
    pass


class SMSValidationError(ATSSMSException):
    pass


def serialize_ats_requests(*ats_serializable_objects):
    """
    Prepares XML with the given ATS elementary requests. The requests must be an instance of a class implementing
    the serialize_ats() method.
    """
    not_serializable = set(request.__class__.__name__ for request in ats_serializable_objects
                           if not hasattr(request, 'serialize_ats'))
    if not_serializable:
        raise SMSSendingError(
            ugettext('Passed classes do not implement serialize_ats() method: {}').format(not_serializable)
        )

    return ''.join(chain(
        (header.format(username=settings.USERNAME, password=settings.PASSWORD),),
        (request.serialize_ats() for request in ats_serializable_objects),
        (footer,),
    ))


def send_ats_requests(*ats_serializable_objects):
    """
    Performs the actual POST request with the given elementary ATS requests.
    """
    requests_xml = serialize_ats_requests(*ats_serializable_objects)
    logged_requests = [request for request in ats_serializable_objects if isinstance(request, models.Model)]
    try:
        return requests.post(settings.URL, data=requests_xml, headers={'Content-Type': 'text/xml'},
                             slug='ATS SMS', related_objects=logged_requests)
    except requests.exceptions.RequestException as e:
        raise SMSSendingError(str(e))


def parse_response_codes(xml):
    """
    Finds all <code> tags in the given XML and returns a mapping "uniq" -> "response code" for all SMS.
    In case of an error, the error is logged.
    """
    soup = BeautifulSoup(xml, 'html.parser')
    code_tags = soup.find_all('code')

    warning_message = ', '.join(
        [(force_text(ATS_STATES.get_label(c))
          if c in ATS_STATES.all
          else 'ATS returned an unknown state {}.'.format(c))
         for c in [int(error_code.string) for error_code in code_tags if not error_code.attrs.get('uniq')]],
    )

    if warning_message:
        LOGGER.warning(warning_message)

    return {
        int(code.attrs['uniq'].lstrip(settings.UNIQ_PREFIX)): int(code.string)
        for code in code_tags if code.attrs.get('uniq')
    }


def send_and_parse_response(*ats_requests):
    """
    Glue function to perform sending ATS requests and parsing the ATS server response in one go.
    """
    return parse_response_codes(send_ats_requests(*ats_requests).text)


def update_sms_states(parsed_response):
    """
    Higher-level function performing serialization of ATS requests, parsing ATS server response and updating
    SMS messages state according the received response.
    """
    for uniq, state in parsed_response.items():
        sms = get_object_or_none(get_output_sms_model(), pk=uniq)
        if sms:
            change_and_save(
                sms, state=state if state in ATS_STATES.all else ATS_STATES.LOCAL_UNKNOWN_ATS_STATE,
                sent_at=timezone.now()
            )
        else:
            raise SMSValidationError(ugettext('SMS with uniq "{}" not found in DB.').format(uniq))


def update_sms_state_from_response(output_sms, parsed_response):
    if output_sms.pk in parsed_response:
        state = parsed_response[output_sms.pk]
        output_sms.state = state if state in ATS_STATES.all else ATS_STATES.LOCAL_UNKNOWN_ATS_STATE
        output_sms.sent_at = timezone.now()
    else:
        raise SMSSendingError(ugettext('ATS response misses status code of SMS with uniq {}').format(output_sms.pk))


def send_and_update_sms_states(*ats_requests):
    """
    Glue function to perform sending ATS requests and updating the corresponsing SMS states in one go.
    """
    update_sms_states(send_and_parse_response(*ats_requests))


def send_multiple(*multiple_output_sms):
    mutiple_output_sms_to_sent = [
        output_sms for output_sms in multiple_output_sms if output_sms.state == ATS_STATES.PROCESSING
    ]
    try:
        parsed_response = send_and_parse_response(*mutiple_output_sms_to_sent)
        for output_sms in mutiple_output_sms_to_sent:
            try:
                update_sms_state_from_response(output_sms, parsed_response)
                output_sms.save()
            except SMSSendingError:
                change_and_save(output_sms, state = ATS_STATES.LOCAL_TO_SEND)
    except SMSSendingError:
        bulk_change_and_save(mutiple_output_sms_to_sent, ATS_STATES.LOCAL_TO_SEND)


def send(output_sms):
    try:
        if output_sms.state == ATS_STATES.PROCESSING:
            parsed_response = send_and_parse_response(output_sms)
            update_sms_state_from_response(output_sms, parsed_response)
            output_sms.save()
        return output_sms
    except SMSSendingError:
        change_and_save(output_sms, state=ATS_STATES.LOCAL_TO_SEND)
        raise


def send_template(recipient, slug='', context=None, **sms_attrs):
    """
    Use this function to send an SMS template to a given number.
    """
    context = context or {}
    try:
        sms_template = get_sms_template_model().objects.get(slug=slug)
        output_sms = get_output_sms_model().objects.create(
            recipient=recipient,
            template_slug=slug,
            content=Template(sms_template.body).render(Context(context)),
            state=(ATS_STATES.DEBUG if settings.DEBUG and recipient not in settings.WHITELIST
                   else ATS_STATES.PROCESSING),
            **sms_attrs
        )
        return send(output_sms)
    except get_sms_template_model().DoesNotExist:
        LOGGER.error(ugettext('SMS message template with slug {slug} does not exist. '
                              'The message to {recipient} cannot be sent.').format(recipient=recipient, slug=slug))
        raise SMSSendingError(ugettext('SMS message template with slug {} does not exist').format(slug))
