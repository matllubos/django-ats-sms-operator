from __future__ import unicode_literals

from django.conf import settings

from is_core.main import UIRESTModelISCore

from ats_sms_operator import config

from .views import OutputATSSMSMessageAddView


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
    ui_add_view = OutputATSSMSMessageAddView
    update_permission = False
    delete_permission = False

    def get_form_fields(self, request, obj=None):
        return (
            super(OutputATSSMSmesssageISCore, self).get_form_fields(request, obj) if obj else ('recipient', 'content')
        )


class SMSTemplateISCore(UIRESTModelISCore):
    model = config.get_sms_template_model()
    abstract = True
