from django.contrib import admin
from .models import Category, Memory, MemoryDetail, Tag, MemoryImage, ChatSession


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'color_code')
    search_fields = ('name', 'user__email')
    list_filter = ('user',)


class MemoryDetailInline(admin.StackedInline):
    model = MemoryDetail
    can_delete = False
    verbose_name = '상세 본문'


class TagInline(admin.TabularInline):
    model = Tag
    extra = 1


class MemoryImageInline(admin.TabularInline):
    model = MemoryImage
    extra = 0


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'mood', 'weather', 'visited_at', 'created_at')
    list_filter = ('mood', 'weather', 'visited_at')
    search_fields = ('title', 'user__email', 'user__nickname')
    ordering = ('-visited_at',)
    inlines = [MemoryDetailInline, TagInline, MemoryImageInline]


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__email', 'query_text')
    ordering = ('-created_at',)
