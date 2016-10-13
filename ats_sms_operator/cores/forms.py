from phonenumber_field import phonenumber

from collections import OrderedDict

from django.forms import CharField, ValidationError
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from is_core.forms.widgets import MultipleTextInput
from is_core.forms.models import SmartModelForm

from chamber.shortcuts import bulk_save


def normalize_phone_number(number):
    if number:
        number = number.replace(' ', '').replace('-', '')
        if len(number) == 9:
            number = ''.join((getattr(settings, 'ATS_SMS_DEFAULT_CALLING_CODE', '+420'), number))
        elif len(number) == 14 and number.startswith('00'):
            number = '+' + number[2:]
    return number


class MultiplePhoneField(CharField):
    default_error_messages = {
        'invalid_phones': _('Some phone number are not valid. Invalid phone numbers: {}.'),
    }

    def __init__(self, *args, **kwargs):
        kwargs['widget'] = kwargs.get('widget', MultipleTextInput(separator=';'))
        super(MultiplePhoneField, self).__init__(*args, **kwargs)

    def clean(self, phones):
        normalized_phones = list(OrderedDict.fromkeys(normalize_phone_number(phone) for phone in phones))
        invalid_phones = [phone for phone in normalized_phones if not phonenumber.to_python(phone).is_valid()]
        if invalid_phones:
            raise ValidationError(self.default_error_messages['invalid_phones'].format(', '.join(invalid_phones)))
        return normalized_phones


class MultipleOutputSMSModelForm(SmartModelForm):

    recipients = MultiplePhoneField(label=_('recipients'))

    def save(self, commit=True):
        sms = super(MultipleOutputSMSModelForm, self).save(commit=False)
        copied_sms_fields = {field_name: getattr(sms, field_name)
                             for field_name in set(self.fields.keys())  - {'recipients'}}
        multiple_sms = [
            self._meta.model(recipient=recipient, **copied_sms_fields)
            for recipient in self.cleaned_data['recipients']
        ]
        if commit:
            bulk_save(multiple_sms)
        return multiple_sms
