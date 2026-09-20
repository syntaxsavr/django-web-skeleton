"""Contact form with the full anti-spam stack: honeypot, signed time-trap,
Turnstile token field. Validation of the traps happens in the view because
each failure must be handled silently (bots get a fake success)."""

from django import forms

from core.models import ContactMessage


class ContactForm(forms.ModelForm):
    website = forms.CharField(  # honeypot: humans never see or fill this
        required=False,
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off", "aria-hidden": "true"}),
    )
    form_ts = forms.CharField(widget=forms.HiddenInput)  # signed at render time in the view
    cf_turnstile_response = forms.CharField(widget=forms.HiddenInput, required=False)
    consent = forms.BooleanField(
        required=True,
        label="I agree that my details are stored to answer this request.",
    )

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "preference", "message"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 6}),
        }

    def clean_website(self):
        value = self.cleaned_data.get("website", "")
        if value:
            raise forms.ValidationError("Spam detected.")
        return value


class RegistrationForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Repeat password")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") and cleaned.get("password2") and cleaned["password1"] != cleaned["password2"]:
            raise forms.ValidationError("The two passwords do not match.")
        return cleaned
