from __future__ import unicode_literals

import six

from django.conf import settings
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from chamber.models import SmartModel
from chamber.utils import remove_accent

from ats_sms_operator import config
from ats_sms_operator.config import ATS_STATES

from ats_sms_operator.utils.compatibility import unescape


@python_2_unicode_compatible
class AbstractInputATSSMSmessage(SmartModel):

    received_at = models.DateTimeField(verbose_name=_('received at'), null=False, blank=False)
    uniq = models.PositiveIntegerField(verbose_name=_('uniq'), null=False, blank=False, unique=True)
    sender = models.CharField(verbose_name=_('sender'), null=False, blank=False, max_length=20)
    recipient = models.CharField(verbose_name=_('recipient'), null=False, blank=False, max_length=20)
    okey = models.CharField(verbose_name=_('okey'), null=False, blank=False, max_length=255)
    opid = models.CharField(verbose_name=_('opid'), null=False, blank=False, max_length=255)
    opmid = models.CharField(verbose_name=_('opmid'), null=False, blank=True, max_length=255)
    content = models.TextField(verbose_name=_('content'), null=False, blank=True)

    def __str__(self):
        return self.sender

    class Meta:
        abstract = True
        verbose_name = _('input ATS message')
        verbose_name_plural = _('input ATS messages')
        ordering = ('-created_at',)


@python_2_unicode_compatible
class AbstractOutputATSSMSmessage(SmartModel):

    STATE = ATS_STATES

    sent_at = models.DateTimeField(verbose_name=_('sent at'), null=True, blank=True)
    sender = models.CharField(verbose_name=_('sender'), null=False, blank=False, max_length=20)
    recipient = models.CharField(verbose_name=_('recipient'), null=False, blank=False, max_length=20)
    opmid = models.CharField(verbose_name=_('opmid'), null=False, blank=True, max_length=255, default='')
    dlr = models.BooleanField(verbose_name=_('require delivery notification?'), null=False, blank=False, default=True)
    validity = models.PositiveIntegerField(verbose_name=_('validity in minutes'), null=False, blank=False, default=60)
    kw = models.CharField(verbose_name=_('project keyword'), null=False, blank=False, max_length=255)
    lower_priority = models.BooleanField(verbose_name=_('lower priority'), null=False, blank=False, default=True)
    billing = models.BooleanField(verbose_name=_('billing'), null=False, blank=False, default=False)
    content = models.TextField(verbose_name=_('content'), null=False, blank=False, max_length=700)
    state = models.IntegerField(verbose_name=_('state'), null=False, blank=False, choices=STATE.choices,
                                default=STATE.LOCAL_TO_SEND)
    template_slug = models.SlugField(max_length=100, null=True, blank=True, verbose_name=_('slug'))

    def clean_content(self):
        if getattr(settings, 'ATS_SMS_OPERATOR_UNESCAPE_HTML', True):
            self.content = unescape(self.content)
        if not config.ATS_USE_ACCENT:
            self.content = six.text_type(remove_accent(six.text_type(self.content)))

    def clean_sender(self):
        self.sender = ''.join(self.sender.split())

    def _pre_save(self, change, *args, **kwargs):
        super(AbstractOutputATSSMSmessage, self)._pre_save(change, *args, **kwargs)
        self.sender = self.sender or config.ATS_OUTPUT_SENDER_NUMBER
        self.kw = self.kw or config.ATS_PROJECT_KEYWORD

    def serialize_ats(self):
        return """<sms type="text" uniq="{prefix}{uniq}" sender="{sender}" recipient="{recipient}" opmid="{opmid}"
                      dlr="{dlr}" validity="{validity}" kw="{kw}">
                        <body order="0" billing="{billing}">{content}</body>
                  </sms>""".format(prefix=config.ATS_UNIQ_PREFIX, uniq=self.pk, sender=self.sender,
                                   recipient=self.recipient, opmid=self.opmid, dlr=int(self.dlr),
                                   validity=self.validity, kw=self.kw, billing=int(self.billing),
                                   content=self.ascii_content)

    @property
    def ascii_content(self):
        return remove_accent(self.content)

    @property
    def failed(self):
        return self.state >= 100 or self.state in (self.STATE.REGISTRATION_OK, self.STATE.REREGISTRATION_OK,
                                                   self.STATE.UNSPECIFIED_ERROR, self.STATE.LOCAL_UNKNOWN_ATS_STATE)

    def __str__(self):
        return self.recipient

    class Meta:
        abstract = True
        verbose_name = _('output ATS message')
        verbose_name_plural = _('output ATS messages')
        ordering = ('-created_at',)

    class UIMeta:
        add_button_verbose_name = _('send new SMS')


@python_2_unicode_compatible
class AbstractSMSTemplate(SmartModel):
    slug = models.SlugField(max_length=100, null=False, blank=False, primary_key=True, verbose_name=_('slug'))
    body = models.TextField(null=True, blank=False, verbose_name=_('message body'))

    def __str__(self):
        return self.slug

    class Meta:
        abstract = True
        verbose_name = _('SMS template')
        verbose_name_plural = _('SMS templates')
