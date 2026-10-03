from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import SubscriptionPlan


class SchoolRegistrationForm(UserCreationForm):
    """Form for registering a new school account."""
    school_name = forms.CharField(
        max_length=200, 
        label='School Name',
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'e.g. Muhu Senior School'})
    )
    school_address = forms.CharField(
        max_length=500, 
        required=False,
        label='School Address',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional'})
    )
    phone = forms.CharField(
        max_length=20, 
        label='Phone Number',
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'e.g. 0712345678'})
    )
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'school@example.com'})
    )
    principal_name = forms.CharField(
        max_length=200, 
        required=False,
        label="Principal's Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Choose a username'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control form-control-lg', 'placeholder': 'Create a password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control form-control-lg', 'placeholder': 'Confirm password'})


class SubscriptionPlanForm(forms.ModelForm):
    """Form for admin to create/edit subscription plans."""
    class Meta:
        model = SubscriptionPlan
        fields = ('name', 'duration', 'amount', 'max_teachers', 'max_classes', 'description', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'e.g. Premium Plan'}),
            'duration': forms.Select(attrs={'class': 'form-select form-control-lg'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'e.g. 5000'}),
            'max_teachers': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0 = unlimited'}),
            'max_classes': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0 = unlimited'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe what this plan includes...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SubscriptionPaymentForm(forms.Form):
    """Form for M-Pesa payment during subscription."""
    phone_number = forms.CharField(
        max_length=20,
        label='M-Pesa Phone Number',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'e.g. 0712345678',
            'required': True,
        })
    )