from __future__ import unicode_literals

from django.conf import settings

from is_core.main import UIRESTModelISCore

from ats_sms_operator import config
from ats_sms_operator.sender import send


class InputATSSMSmessageISCore(UIRESTModelISCore):

    model = config.get_input_sms_model()
    list_display = ('created_at', 'received_at', 'sender', 'recipient', 'uniq', 'content')
    abstract = True
    form_fields = ('created_at', 'received_at', 'sender', 'recipient', 'uniq', 'okey', 'opid', 'opmid', 'content')
    create_permission = False
    update_permission = False
    delete_permission = False


class OutputATSSMSmesssageISCore(UIRESTModelISCore):

    model = config.get_output_sms_model()
    list_display = ('created_at', 'sent_at', 'sender', 'recipient', 'content', 'state')
    abstract = True
    update_permission = False
    delete_permission = False

    def get_ui_form_fields(self, request, obj=None):
        return (
            super(OutputATSSMSmesssageISCore, self).get_ui_form_fields(request, obj=obj)
            if obj else ('recipient', 'content')
        )

    def pre_save_model(self, request, obj, form, change):
        obj.state = (
            config.ATS_STATES.DEBUG if settings.ATS_SMS_DEBUG and obj.recipient not in config.ATS_WHITELIST
            else config.ATS_STATES.PROCESSING
        )

    def post_save_model(self, request, obj, form, change):
        send(obj)


class SMSTemplateISCore(UIRESTModelISCore):

    model = config.get_sms_template_model()
    abstract = True
