from phonenumber_field import phonenumber

from collections import OrderedDict

from django.forms import CharField, ValidationError
from django.utils.translation import ugettext_lazy as _

from is_core.forms.widgets import MultipleTextInput
from is_core.forms.models import SmartModelForm

from chamber.shortcuts import bulk_save

from ats_sms_operator.config import settings


def normalize_phone_number(number):
    if number:
        number = number.replace(' ', '').replace('-', '')
        if len(number) == 9:
            number = ''.join((settings.DEFAULT_CALLING_CODE, number))
        elif len(number) == 14 and number.startswith('00'):
            number = '+' + number[2:]
    return number


class MultiplePhoneField(CharField):
    default_error_messages = {
        'invalid_phones': _('Some phone number are not valid. Invalid phone numbers: {}.'),
        'required': _('This field is required.'),
    }

    def __init__(self, *args, **kwargs):
        kwargs['widget'] = kwargs.get('widget', MultipleTextInput(separator=';'))
        super(MultiplePhoneField, self).__init__(*args, **kwargs)

    def clean(self, phones):
        normalized_phones = list(OrderedDict.fromkeys(normalize_phone_number(phone) for phone in phones
                                                      if normalize_phone_number(phone)))
        invalid_phones = [phone for phone in normalized_phones if not phonenumber.to_python(phone).is_valid()]
        if invalid_phones:
            raise ValidationError(self.default_error_messages['invalid_phones'].format(', '.join(invalid_phones)))
        if not normalized_phones and self.required:
            raise ValidationError(self.default_error_messages['required'])

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
