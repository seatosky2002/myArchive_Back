from django.urls import path
from . import views

urlpatterns = [
    # 그룹 목록 / 생성
    path('',                                views.GroupListCreateView.as_view(),   name='group-list'),
    # 초대 코드로 가입 (POST /groups/join/)
    path('join/',                           views.JoinByCodeView.as_view(),        name='group-join'),
    # 그룹 상세 / 수정 / 삭제
    path('<uuid:pk>/',                      views.GroupDetailView.as_view(),       name='group-detail'),
    # 멤버 목록
    path('<uuid:pk>/members/',              views.GroupMemberListView.as_view(),   name='group-members'),
    # 멤버 역할 변경 / 추방
    path('<uuid:pk>/members/<uuid:user_id>/', views.GroupMemberDetailView.as_view(), name='group-member-detail'),
    # 탈퇴
    path('<uuid:pk>/leave/',                views.LeaveGroupView.as_view(),        name='group-leave'),
    # owner 양도
    path('<uuid:pk>/transfer-owner/',       views.TransferOwnerView.as_view(),     name='group-transfer-owner'),
    # 초대 코드 재발급
    path('<uuid:pk>/reset-invite-code/',    views.ResetInviteCodeView.as_view(),   name='group-reset-invite'),
    # 그룹 활동 로그 (admin 이상)
    path('<uuid:pk>/activities/',                        views.GroupActivityListView.as_view(),       name='group-activities'),
    # 그룹 카테고리 목록 / 생성
    path('<uuid:pk>/categories/',                        views.GroupCategoryListCreateView.as_view(), name='group-categories'),
    # 그룹 카테고리 수정 / 삭제
    path('<uuid:pk>/categories/<int:category_id>/',      views.GroupCategoryDetailView.as_view(),     name='group-category-detail'),
    # 그룹 기억 목록
    path('<uuid:pk>/memories/',             views.GroupMemoryListView.as_view(),   name='group-memories'),
]
