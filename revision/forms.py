from django import forms
from .models import Subject, RevisionMaterial, Class


class SchemeOfWorkGeneratorForm(forms.Form):
    class_ref = forms.ModelChoiceField(
        queryset=Class.objects.all().order_by('curriculum', 'level', 'name'),
        label='Class',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all().order_by('name'),
        label='Subject',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    term = forms.ChoiceField(
        choices=RevisionMaterial.TERM_CHOICES,
        label='Term',
        initial='term1',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    weeks_count = forms.IntegerField(
        required=True,
        label='Number of Weeks',
        min_value=1,
        max_value=52,
        initial=12,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 12'}),
    )
    topics = forms.CharField(
        required=False,
        label='Topics (one per line)',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Enter topics or learning outcomes, one per line...'}),
        help_text='List the topics or learning outcomes to include in the scheme.',
    )
    objectives = forms.CharField(
        required=False,
        label='General Objectives',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter overall learning objectives...'}),
    )
