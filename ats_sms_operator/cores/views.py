from __future__ import unicode_literals

from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _

from is_core.generic_views.form_views import AddModelFormView

from ats_sms_operator.config import ATS_STATES, settings
from ats_sms_operator.sender import send_multiple

from .forms import MultipleOutputSMSModelForm


class OutputATSSMSMessageAddView(AddModelFormView):

    form_class = MultipleOutputSMSModelForm
    fields = ('recipients', 'content')

    messages = {
        'success': _('The SMS to recipients %(recipients)s was successfully sent.'),
        'error': _('Please correct the error below.')
    }

    def get_message_kwargs(self, objs):
        return {'recipients': ', '.join(force_text(obj.recipient) for obj in objs)}

    def save_form(self, form, **kwargs):
        objs = form.save(commit=False)
        for obj in objs:
            obj.state = (ATS_STATES.DEBUG if settings.DEBUG and obj.recipient not in settings.WHITELIST
                         else ATS_STATES.PROCESSING)
            obj.save()
        send_multiple(*objs)
        return objs

    def get_success_url(self, objs):
        if ('list' in self.core.ui_patterns and
                self.core.ui_patterns.get('list').get_view(self.request).has_get_permission() and
                'save' in self.request.POST):
            return self.core.ui_patterns.get('list').get_url_string(self.request)
        elif (len(objs) == 1 and 'edit' in self.core.ui_patterns and
                self.core.ui_patterns.get('edit').get_view(self.request).has_get_permission(obj=objs[0]) and
                'save-and-continue' in self.request.POST):
            return self.core.ui_patterns.get('edit').get_url_string(self.request, kwargs={'pk': objs[0].pk})
        else:
            return self.request.get_full_path()
