from django import forms
from .models import Registration, TicketConfirmation


class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = ['name', 'srn', 'prn', 'year', 'email', 'phone', 'hostelite', 'hostel_block', 'room_number']
        widgets = {
            'year': forms.Select(attrs={'class': 'form-select'}),
            'hostelite': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'srn': forms.TextInput(attrs={'class': 'form-input'}),
            'prn': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'hostel_block': forms.TextInput(attrs={'class': 'form-input'}),
            'room_number': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        hostelite = cleaned_data.get('hostelite')
        if hostelite == 'Yes':
            if not cleaned_data.get('hostel_block'):
                self.add_error('hostel_block', "Hostel block/unit is required if hostelite is Yes.")
            if not cleaned_data.get('room_number'):
                self.add_error('room_number', "Room number is required if hostelite is Yes.")
        return cleaned_data



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
