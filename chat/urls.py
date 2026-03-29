"""
chat/urls.py — 챗봇 URL 라우팅
"""
from django.urls import path
from .views import ChatView, ChatHistoryView

urlpatterns = [
    path('', ChatView.as_view()),               # POST /api/chat/
    path('history/', ChatHistoryView.as_view()), # GET  /api/chat/history/
]
