from django.contrib import admin

from .models import Document, Summary, SummarySentence, Tag, UserProfile, UserSetting

admin.site.site_header = "Trang quản trị SummarEase"
admin.site.site_title = "Quản trị SummarEase"
admin.site.index_title = "Quản trị hệ thống tóm tắt"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")


@admin.register(UserSetting)
class UserSettingAdmin(admin.ModelAdmin):
    list_display = ("user", "default_summary_ratio", "language_preference", "gemini_api_key")
    search_fields = ("user__username",)


class SummarySentenceInline(admin.TabularInline):
    model = SummarySentence
    extra = 0


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "source_type", "created_at")
    search_fields = ("title", "source_name", "content")


@admin.register(Summary)
class SummaryAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "method", "language", "ratio", "created_at")
    list_filter = ("method", "language")
    search_fields = ("title", "summary_text", "document__content")
    inlines = [SummarySentenceInline]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ("name",)
