from django import forms
from django.utils.translation import gettext_lazy as _
from trackable.organizations.models import Organization
from trackable.accounts.models import User
from trackable.core.models import Holiday


class OrganizationBrandingForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "logo", "favicon", "apple_touch_icon",
            "primary_color", "accent_color", "custom_css",
        ]
        widgets = {
            "primary_color": forms.TextInput(attrs={
                "type": "color",
                "style": "width:60px; height:44px; padding:4px; cursor:pointer;",
            }),
            "accent_color": forms.TextInput(attrs={
                "type": "color",
                "style": "width:60px; height:44px; padding:4px; cursor:pointer;",
            }),
            "custom_css": forms.Textarea(attrs={
                "rows": 10,
                "class": "form-control css-editor",
                "placeholder": _("/* Custom CSS rules */"),
                "style": "font-family:monospace; font-size:.88rem;",
            }),
        }
        help_texts = {
            "logo": _("Empfohlen: 180×40 px, PNG oder SVG. Ersetzt das Logo in der Navigationsleiste."),
            "favicon": _("Empfohlen: 32×32 px, ICO oder PNG."),
            "apple_touch_icon": _("Empfohlen: 180×180 px, PNG. iOS-Homescreen-Symbol."),
            "primary_color": _("Hex-Farbe (#RRGGBB). Überschreibt primäre UI-Akzente (Buttons, Badges)."),
            "accent_color": _("Hex-Farbe (#RRGGBB). Überschreibt sekundäre Akzente (Links, Hover)."),
            "custom_css": _("Beliebige CSS-Regeln (z. B. .btn-primary { background: #xyz; }). Wird nach allen Standard-Styles geladen."),
        }


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ["name"]
        labels = {"name": _("Organization name")}


class EmployeeCreateForm(forms.ModelForm):
    temp_password = forms.CharField(
        widget=forms.PasswordInput,
        label=_("Temporary password"),
    )
    temp_password_confirm = forms.CharField(
        widget=forms.PasswordInput,
        label=_("Confirm temporary password"),
    )

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name"]
        labels = {
            "username": _("Username"),
            "email": _("E-Mail"),
            "first_name": _("First name"),
            "last_name": _("Last name"),
        }

    def clean(self):
        cleaned_data = super().clean()
        pw = cleaned_data.get("temp_password")
        pw_confirm = cleaned_data.get("temp_password_confirm")
        if pw and pw_confirm and pw != pw_confirm:
            raise forms.ValidationError(_("Passwords do not match."))
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["temp_password"])
        user.email_confirmed = True
        if commit:
            user.save()
        return user


class HolidayForm(forms.ModelForm):
    class Meta:
        model = Holiday
        fields = ["date", "name"]
        labels = {
            "date": _("Date"),
            "name": _("Holiday name"),
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }
