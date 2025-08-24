from django import forms
from .models import Registration, TicketConfirmation

class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = ['name', 'srn', 'prn', 'year', 'email', 'phone']
        widgets = {
            'year': forms.Select()
        }

class TicketConfirmationForm(forms.ModelForm):
    class Meta:
        model = TicketConfirmation
        fields = ['payment_type', 'utr_number']

    def clean(self):
        cleaned_data = super().clean()
        payment_type = cleaned_data.get('payment_type')
        utr_number = cleaned_data.get('utr_number')

        if payment_type == 'UPI' and not utr_number:
            raise forms.ValidationError("UTR number is required for UPI payments.")
        if payment_type == 'Cash':
            cleaned_data['utr_number'] = ''
        return cleaned_data
