from __future__ import unicode_literals

from django.conf import settings as django_settings
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from chamber.utils.datastructures import ChoicesNumEnum


try:
    from django.apps import apps
    get_model = apps.get_model
except ImportError:
    from django.db.models.loading import get_model


DEFAULTS = {
    'SENDER_IP': '80.188.94.234',
    'OUTPUT_SENDER_NUMBER': None,
    'PROJECT_KEYWORD': None,
    'USERNAME': None,
    'PASSWORD': None,
    'URL': 'https://fik.atspraha.cz/gwfcgi/XMLServerWrapper.fcgi',
    'USE_ACCENT': False,
    'WHITELIST': (),
    'PROCESSING_TIMEOUT': 10,
    'UNIQ_PREFIX': '',  # To mitigate conflicts in uniqs on production and accept
    'TEXTID': None,
    'OPERATOR_UNESCAPE_HTML': True,
    'DEBUG': False,
    'INPUT_SMS_MODEL': None,
    'OUTPUT_SMS_MODEL': None,
    'TEMPLATE_MODEL': None,
    'DEFAULT_CALLING_CODE': '+420',
    'LOG_IDLE_MESSAGES': True,
    'IDLE_MESSAGES_TIMEOUT_MINUTES': 10,
}


ATS_STATES = ChoicesNumEnum(
    # Registration
    ('REGISTRATION_OK', _('registration successful'), 10),
    ('REREGISTRATION_OK', _('re-registration successful'), 11),
    # SMS delivery receipts
    ('NOT_FOUND', _('not found'), 20),
    ('NOT_SENT', _('not sent yet'), 21),
    ('SENT', _('sent'), 22),
    ('DELIVERED', _('delivered'), 23),
    ('NOT_DELIVERED', _('not delivered'), 24),
    ('UNKNOWN', _('not able to determine the state'), 25),
    # Authentication
    ('AUTHENTICATION_FAILED', _('authentication failed'), 100),
    # Internal errors
    ('DB_ERROR', _('DB error'), 200),
    # Request states
    ('OK', _('SMS is OK and ready to be sent'), 0),
    ('UNSPECIFIED_ERROR', _('unspecified error'), 1),
    ('BATCH_WITH_NOT_UNIQUE_UNIQ', _('one of the requests has not unique "uniq"'), 300),
    ('SMS_NOT_UNIQUE_UNIQ', _('SMS has not unique "uniq"'), 310),
    ('SMS_NO_KW', _('SMS lacks keyword'), 320),
    ('KW_INVALID', _('keyword not valid'), 321),
    ('NO_SENDER', _('no sender specified'), 330),
    ('SENDER_INVALID', _('sender not valid'), 331),
    ('MO_PR_NOT_ALLOWED', _('MO PR SMS not allowed'), 332),
    ('MT_PR_NOT_ALLOWED', _('MT PR SMS not allowed'), 333),
    ('MT_PR_DAILY_LIMIT', _('MT PR SMS daily limit exceeded'), 334),
    ('MT_PR_TOTAL_LIMIT', _('MT PR SMS total limit exceeded'), 335),
    ('GEOGRAPHIC_NOT_ALLOWED', _('geographic number is not allowed'), 336),
    ('MT_SK_NOT_ALLOWED', _('MT SMS to Slovakia not allowed'), 337),
    ('SHORTCODES_NOT_ALLOWED', _('shortcodes not allowed'), 338),
    ('UNKNOWN_SENDER', _('sender is unknown'), 339),
    ('UNSPECIFIED_SMS_TYPE', _('type of SMS not specified'), 340),
    ('TOO_LONG', _('SMS too long'), 341),
    ('TOO_MANY_PARTS', _('too many SMS parts (max. is 10)'), 342),
    ('WRONG_SENDER_OR_RECEIVER', _('wrong number of sender/receiver'), 343),
    ('NO_RECIPIENT_OR_WRONG_FORMAT', _('recipient is missing or in wrong format'), 350),
    ('TEXTID_NOT_ALLOWED', _('using "textid" is not allowed'), 360),
    ('WRONG_TEXTID', _('"textid" is in wrong format'), 361),
    ('LONG_SMS_TEXTID_NOT_ALLOWED', _('long SMS with "textid" not allowed'), 362),
    # XML errors
    ('XML_MISSING', _('XML body missing'), 701),
    ('XML_UNREADABLE', _('XML is not readable'), 702),
    ('WRONG_HTTP_METHOD', _('unknown HTTP method or not HTTP POST'), 703),
    ('XML_INVALID', _('XML invalid'), 705),
    # Local states not mapped to ATS states
    ('LOCAL_UNKNOWN_ATS_STATE', _('ATS returned state not known to us'), -1),
    ('LOCAL_TO_SEND', _('to be sent to ATS'), -2),
    ('DEBUG', _('debug SMS'), -3),
    ('PROCESSING', _('processing'), -4),
    ('LOCAL_ERROR', _('local error'), -5),
    ('TIMEOUT', _('timeout'), -6),
)


class Settings(object):

    def __getattr__(self, attr):
        if attr not in DEFAULTS:
            raise AttributeError('Invalid ATS_SMS setting: "{}"'.format(attr))

        default = DEFAULTS[attr]
        return getattr(django_settings, 'ATS_SMS_{}'.format(attr), default(self) if callable(default) else default)


settings = Settings()


def get_input_sms_model():
    return get_model(*settings.INPUT_SMS_MODEL.split('.'))


def get_output_sms_model():
    return get_model(*settings.OUTPUT_SMS_MODEL.split('.'))


def get_sms_template_model():
    return get_model(*settings.TEMPLATE_MODEL.split('.'))
