from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Tên đăng nhập")
    password = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput)


class SummaryRequestForm(forms.Form):
    SOURCE_CHOICES = (
        ("text", "Văn bản"),
        ("file", "Tệp"),
        ("url", "URL"),
    )

    METHOD_CHOICES = (
        ("textrank", "TextRank"),
        ("gemini", "Gemini"),
    )

    source_type = forms.ChoiceField(choices=SOURCE_CHOICES)
    method = forms.ChoiceField(choices=METHOD_CHOICES)
    text = forms.CharField(required=False, widget=forms.Textarea)
    source_url = forms.URLField(required=False)
    upload = forms.FileField(required=False)
    ratio = forms.FloatField(min_value=0.0, max_value=1.0, required=False)

    def clean_ratio(self):
        return self.cleaned_data.get("ratio") or 0.2

    def clean(self):
        cleaned = super().clean()
        source_type = cleaned.get("source_type")
        text = (cleaned.get("text") or "").strip()
        source_url = (cleaned.get("source_url") or "").strip()
        upload = cleaned.get("upload")

        if source_type == "text" and not text:
            self.add_error("text", "Nhập văn bản cần tóm tắt.")
        if source_type == "url" and not source_url:
            self.add_error("source_url", "Nhập URL hợp lệ.")
        if source_type == "file" and not upload:
            self.add_error("upload", "Chọn tệp để tóm tắt.")
        return cleaned
