from django.apps import AppConfig


class MemoriesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'memories'

    def ready(self):
        # 시그널 연결 — 앱 로드 완료 후 등록
        from django.db.models.signals import post_save
        from .models import MemoryDetail
        from .signals import auto_embed_on_save

        post_save.connect(auto_embed_on_save, sender=MemoryDetail)
