# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from six import StringIO

from datetime import timedelta

import requests
import responses

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from germanium.anotations import data_provider, turn_off_auto_now
from germanium.tools import assert_equal, assert_false, assert_is_not_none, assert_raises, assert_true

from ats_sms_operator.config import ATS_STATES
from ats_sms_operator.sender import (SMSSendingError, SMSValidationError, parse_response_codes,
                                     send_and_update_sms_states, send_ats_requests, send_template,
                                     serialize_ats_requests)

from sender.models import OutputSMS

from .models.factories import OutputSMSFactory, SMSTemplateFactory


# TODO remove this when the function is added to chamber
def strip_all(txt):
    return ''.join(txt.split())


class OutputSMSTestCase(TestCase):

    ATS_SERIALIZED_SMS = """<sms type="text" uniq="{prefix}{uniq}" sender="22222" recipient="+420731545945" opmid=""
                             dlr="1" validity="60" kw="22222EEEEE" textid="{textid}">
                             <body order="0" billing="0">TEXT1</body>
                             </sms>"""

    ATS_SMS_REQUEST = """<?xml version="1.0" encoding="UTF-8" ?>
                         <messages>
                            <auth>
                                <name>ats-library</name>
                                <password>aaaaabbbbbcccccddddd</password>
                            </auth>
                            <sms type="text" uniq="{prefix}{uniq1}" sender="22222" recipient="+420731545945" opmid=""
                             dlr="1" validity="60" kw="22222EEEEE" textid="{textid}">
                                <body order="0" billing="0">TEXT1</body>
                            </sms>
                            <sms type="text" uniq="{prefix}{uniq2}" sender="22222" recipient="+420777555444" opmid=""
                             dlr="1" validity="60" kw="22222EEEEE" textid="{textid}">
                                <body order="0" billing="0">TEXT2</body>
                            </sms>
                         </messages>"""

    ATS_SMS_REQUEST_RESPONSE_SENT = """<?xml version="1.0" encoding="UTF-8" ?>
                                       <status>
                                            <code uniq="{prefix}{uniq1}">0</code>
                                            <code uniq="{prefix}{uniq2}">123456</code>
                                            <d></d>
                                       </status>"""

    ATS_SINGLE_SMS_REQUEST_RESPONSE_SENT = """<?xml version="1.0" encoding="UTF-8" ?>
                                              <status>
                                                  <code uniq="{}">0</code>
                                                  <d></d>
                                              </status>"""

    ATS_SMS_DELIVERY_REQUEST = """<?xml version="1.0" encoding="UTF-8" ?>
                                  <messages>
                                      <auth>
                                          <name>ats-library</name>
                                          <password>aaaaabbbbbcccccddddd</password>
                                      </auth>
                                  <dlr uniq="{prefix}{uniq1}">{prefix}{uniq1}</dlr>
                                  <dlr uniq="{prefix}{uniq2}">{prefix}{uniq2}</dlr>
                                  </messages>"""

    ATS_SMS_DELIVERY_RESPONSE = """<?xml version="1.0" encoding="UTF-8" ?>
                                   <status>
                                       <code uniq="{prefix}{uniq1}">22</code>
                                       <code uniq="{prefix}{uniq2}">23</code>
                                       <d></d>
                                   </status>"""

    ATS_UNKNOW_STATE_RESPONSE = """<?xml version="1.0" encoding="UTF-8" ?>
                                   <status>
                                       <code>999</code>
                                   </status>"""
    ATS_TEST_UNIQ = {
        'uniq1': 245,
        'uniq2': 246,
    }

    ATS_INVALID_UNIQ = {
        'uniq1': 245,
        'uniq2': -5,
    }

    ATS_OUTPUT_SMS1 = {
        'content': 'TĚXT1',
        'recipient': '+420731545945',
        'validity': 60,
        'kw': '22222EEEEE',
        'sender': '22222',
    }

    ATS_OUTPUT_SMS2 = {
        'content': 'TĚXT2',
        'recipient': '+420777555444',
        'validity': 60,
        'kw': '22222EEEEE',
        'sender': '22222',
    }

    def setUp(self):
        super(OutputSMSTestCase, self).setUp()
        SMSTemplateFactory()

    def test_should_serialize_sms_message(self):
        sms = OutputSMSFactory(**self.ATS_OUTPUT_SMS1)
        assert_equal(strip_all(sms.serialize_ats()),
                     strip_all(self.ATS_SERIALIZED_SMS.format(prefix=settings.ATS_UNIQ_PREFIX, uniq=sms.pk, textid=settings.ATS_TEXTID)))

    def test_should_serialize_ats_requests(self):
        sms1 = OutputSMSFactory(**self.ATS_OUTPUT_SMS1)
        sms2 = OutputSMSFactory(**self.ATS_OUTPUT_SMS2)
        assert_equal(strip_all(serialize_ats_requests(sms1, sms2)),
                     strip_all(self.ATS_SMS_REQUEST.format(prefix=settings.ATS_UNIQ_PREFIX, uniq1=sms1.pk,
                                                           uniq2=sms2.pk, textid=settings.ATS_TEXTID)))

    def get_prefixes(self):
        return ('',), (settings.ATS_UNIQ_PREFIX,)

    @responses.activate
    @data_provider(get_prefixes)
    def test_should_send_ats_request_and_parse_response_codes(self, prefix):
        responses.add(responses.POST, settings.ATS_URL, content_type='text/xml', status=200,
                      body=self.ATS_SMS_REQUEST_RESPONSE_SENT.format(prefix=prefix, **self.ATS_TEST_UNIQ))
        sms1 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq1'], **self.ATS_OUTPUT_SMS1)
        sms2 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq2'], **self.ATS_OUTPUT_SMS2)

        response = send_ats_requests(sms1, sms2)

        assert_equal(response.request.url, 'http://fik.atspraha.cz/gwfcgi/XMLServerWrapper.fcgi')
        assert_equal(response.request.headers['content-type'], 'text/xml')

        response_codes = parse_response_codes(response.text)

        assert_equal(response_codes[self.ATS_TEST_UNIQ['uniq1']], 0)
        assert_equal(response_codes[self.ATS_TEST_UNIQ['uniq2']], 123456)

    @responses.activate
    def test_parsing_response_should_raise_exception_if_uniq_does_not_exist(self):
        def raise_exception(request):
            raise requests.exceptions.HTTPError()

        responses.add_callback(responses.POST, settings.ATS_URL, content_type='text/xml', callback=raise_exception)

        sms1 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq1'], **self.ATS_OUTPUT_SMS1)
        sms2 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq2'], **self.ATS_OUTPUT_SMS2)

        assert_raises(SMSSendingError, send_and_update_sms_states, sms1, sms2)

    @responses.activate
    def test_requests_exception_should_be_caught_and_raised(self):
        responses.add(responses.POST, settings.ATS_URL, content_type='text/xml', status=200,
                      body=self.ATS_SMS_REQUEST_RESPONSE_SENT.format(prefix=settings.ATS_UNIQ_PREFIX,
                                                                     **self.ATS_INVALID_UNIQ))
        sms1 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq1'], **self.ATS_OUTPUT_SMS1)
        sms2 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq2'], **self.ATS_OUTPUT_SMS2)

        assert_raises(SMSValidationError, send_and_update_sms_states, sms1, sms2)

    @responses.activate
    def test_command_should_send_and_update_sms(self):
        responses.add(responses.POST, settings.ATS_URL, content_type='text/xml', status=200,
                      body=self.ATS_SMS_REQUEST_RESPONSE_SENT.format(prefix=settings.ATS_UNIQ_PREFIX,
                                                                     **self.ATS_TEST_UNIQ))

        sms1 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq1'], **self.ATS_OUTPUT_SMS1)
        sms2 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq2'], **self.ATS_OUTPUT_SMS2)

        call_command('send_sms', stdout=StringIO(), stderr=StringIO())

        sms1 = OutputSMS.objects.get(pk=sms1.pk)
        sms2 = OutputSMS.objects.get(pk=sms2.pk)

        assert_equal(sms1.state, ATS_STATES.OK)
        assert_is_not_none(sms1.sent_at)
        assert_equal(sms2.state, ATS_STATES.LOCAL_UNKNOWN_ATS_STATE)
        assert_is_not_none(sms2.sent_at)

    @responses.activate
    def test_command_should_check_delivery_status(self):
        responses.add(responses.POST, settings.ATS_URL, content_type='text/xml',
                      body=self.ATS_SMS_DELIVERY_RESPONSE.format(prefix=settings.ATS_UNIQ_PREFIX, **self.ATS_TEST_UNIQ),
                      status=200)

        sms2 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq2'], sent_at=timezone.now(), state=ATS_STATES.OK,
                                **self.ATS_OUTPUT_SMS2)
        sms1 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq1'], sent_at=timezone.now(), state=ATS_STATES.OK,
                                **self.ATS_OUTPUT_SMS1)

        call_command('check_sms_delivery', stdout=StringIO(), stderr=StringIO())

        sms1 = OutputSMS.objects.get(pk=sms1.pk)
        sms2 = OutputSMS.objects.get(pk=sms2.pk)

        assert_equal(strip_all(responses.calls[0].request.body),
                     strip_all(self.ATS_SMS_DELIVERY_REQUEST.format(prefix=settings.ATS_UNIQ_PREFIX,
                                                                    uniq1=self.ATS_TEST_UNIQ['uniq1'],
                                                                    uniq2=self.ATS_TEST_UNIQ['uniq2'])))
        assert_equal(sms1.state, ATS_STATES.SENT)
        assert_equal(sms2.state, ATS_STATES.DELIVERED)

    @responses.activate
    def test_sms_template_should_be_immediately_send(self):
        responses.add(responses.POST, settings.ATS_URL, content_type='text/xml',
                      body=self.ATS_SINGLE_SMS_REQUEST_RESPONSE_SENT.format(245), status=200)
        sms1 = send_template('+420777111222', slug='test', context={'variable': 'context works'}, pk=245)

        sms1 = OutputSMS.objects.get(pk=sms1.pk)

        assert_equal(sms1.state, ATS_STATES.OK)
        assert_true('context works' in sms1.content)
        assert_is_not_none(sms1.sent_at)

    def test_send_command_should_not_send_empty_request(self):
        call_command('send_sms', stdout=StringIO(), stderr=StringIO())

    def test_delivery_command_should_not_send_empty_request(self):
        call_command('check_sms_delivery', stdout=StringIO(), stderr=StringIO())

    @responses.activate
    def test_should_correctly_handle_unknown_ats_state(self):
        responses.add(responses.POST, settings.ATS_URL, content_type='text/xml',
                      body=self.ATS_UNKNOW_STATE_RESPONSE, status=200)
        sms1 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq1'], **self.ATS_OUTPUT_SMS1)
        sms2 = OutputSMSFactory(pk=self.ATS_TEST_UNIQ['uniq2'], **self.ATS_OUTPUT_SMS2)

        response = send_ats_requests(sms1, sms2)
        with open('./var/log/ats_sms.log') as ats_log:
            log_lines_count = sum(1 for _ in ats_log)
            response_codes = parse_response_codes(response.text)
            ats_log.seek(0)
            log_lines = ats_log.readlines()

            assert_equal(log_lines_count + 1, len(log_lines))
            assert_true('999' in log_lines[-1])
            assert_false(response_codes)

    def test_sender_should_not_have_any_spaces(self):
        sms = OutputSMSFactory(sender='222 22')
        assert_equal(sms.sender, '22222')

    @turn_off_auto_now(OutputSMS, 'changed_at')
    def test_processing_sms_is_timeouted(self):
        sms1 = OutputSMSFactory(state=ATS_STATES.PROCESSING, changed_at=timezone.now())
        call_command('clean_processing_sms', stdout=StringIO(), stderr=StringIO())
        assert_equal(OutputSMS.objects.get(pk=sms1.pk).state, ATS_STATES.PROCESSING)
        sms2 = OutputSMSFactory(state=ATS_STATES.PROCESSING, changed_at=timezone.now() - timedelta(seconds=11))
        call_command('clean_processing_sms', stdout=StringIO(), stderr=StringIO())
        assert_equal(OutputSMS.objects.get(pk=sms2.pk).state, ATS_STATES.TIMEOUT)

    @responses.activate
    def test_sms_template_for_unavailable_service_should_create_message_with_state_local_to_send(self):
        def raise_exception(request):
            raise requests.exceptions.HTTPError()

        responses.add_callback(responses.POST, settings.ATS_URL, content_type='text/xml', callback=raise_exception)
        assert_raises(SMSSendingError, send_template, '+420777111222', slug='test',
                      context={'variable': 'context works'}, pk=245)
        assert_equal(OutputSMS.objects.get(pk=245).state, ATS_STATES.LOCAL_TO_SEND)
