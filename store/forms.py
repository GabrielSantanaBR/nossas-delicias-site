from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class RegisterForm(UserCreationForm):
    email=forms.EmailField(required=True); first_name=forms.CharField(max_length=80); last_name=forms.CharField(max_length=80)
    marketing_opt_in=forms.BooleanField(required=False,label='Quero receber ofertas e novidades')
    class Meta:
        model=User; fields=('first_name','last_name','email','username','password1','password2')
    def clean_email(self):
        email=self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists(): raise forms.ValidationError('Já existe uma conta com este e-mail.')
        return email
    def save(self,commit=True):
        user=super().save(commit=False); user.email=self.cleaned_data['email']; user.first_name=self.cleaned_data['first_name']; user.last_name=self.cleaned_data['last_name']
        if commit: user.save()
        return user

class CheckoutForm(forms.Form):
    delivery_date=forms.DateField(widget=forms.DateInput(attrs={'type':'date'})); zip_code=forms.CharField(max_length=10); address=forms.CharField(max_length=240); note=forms.CharField(widget=forms.Textarea,required=False,max_length=1000)
