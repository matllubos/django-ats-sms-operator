from __future__ import unicode_literals

from datetime import datetime
from itertools import chain

from django.db import IntegrityError
from django.utils import timezone
from django.utils.encoding import force_text

from chamber.exceptions import PersistenceException

from bs4 import BeautifulSoup
from ipware.ip import get_ip

from ats_sms_operator.config import ATS_STATES, settings, get_input_sms_model


# TODO remove the try-except once old is-core does not have to be supported
try:
    from is_core.rest.resource import RESTResource
except ImportError:
    from is_core.rest.resource import RestResource as RESTResource


def merge(origin, *args):
    """
    Merges given dictionaries, `origin` will not be changed.
    """
    # TODO remove this once merge is in chamber
    copy = origin.copy()
    for dictionary in args:
        copy.update(dictionary)
    return copy


class InputATSSMSmessageResource(RESTResource):
    login_required = False

    def __init__(self, request, callback_function):
        super(InputATSSMSmessageResource, self).__init__(request)
        self.callback_function = callback_function

    def _deserialize(self):
        soup = BeautifulSoup(force_text(self.request.body), 'html.parser')

        self.request.data = ([merge(msg.attrs, {'content': msg.string or ''}) for msg in soup.messages.find_all('sms')]
                             if soup.messages else ())
        return self.request

    def _serialize(self, result):
        return '\n'.join(chain(
            ('<?xml version="1.0" encoding="UTF-8" ?>', '<status>'),
            ('<code uniq="{}">{}</code>'.format(uniq, code) for code, uniq in result),
            ('</status>',)
        )), 'text/xml'

    def _get_or_create_input_message(self, message):
        try:
            return get_input_sms_model().objects.get_or_create(
                received_at=timezone.make_aware(datetime.strptime(message.get('ts'), "%Y-%m-%d %H:%M:%S"),
                                                timezone.get_default_timezone()),
                **{k: v for k, v in message.items()
                   if k in ('uniq', 'sender', 'recipient', 'okey', 'opid', 'opmid', 'content')}
            )
        except (IntegrityError, TypeError, PersistenceException, ValueError):
            return (None, False)

    def post(self):
        data = self.request.data
        result = []
        for message in data:
            input_message, created = self._get_or_create_input_message(message)
            if input_message:
                self.callback_function(input_message, created)
                result.append((ATS_STATES.DELIVERED, input_message.uniq))
            else:
                result.append((ATS_STATES.NOT_DELIVERED, message.get('uniq', '')))

        return result

    def has_post_permission(self, *args, **kwargs):
        return (super(InputATSSMSmessageResource, self).has_post_permission(*args, **kwargs) and
                (get_ip(self.request) == settings.SENDER_IP or settings.DEBUG))
