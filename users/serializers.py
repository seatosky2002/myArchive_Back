from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """
    유저 정보 읽기용 Serializer.
    비밀번호 등 민감 정보는 포함하지 않음.
    GET /api/users/me/ 응답에 사용.
    """
    class Meta:
        model = User
        fields = ('id', 'email', 'nickname', 'profile_img_url', 'date_joined')
        read_only_fields = ('id', 'date_joined')


class RegisterSerializer(serializers.ModelSerializer):
    """
    회원가입 쓰기용 Serializer.
    password는 write_only로 응답에 포함하지 않고,
    create() 시 set_password()로 해싱 처리.
    """
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('email', 'password', 'nickname')

    def create(self, validated_data):
        # create_user()를 사용해 password 자동 해싱
        user = User.objects.create_user(
            username=validated_data['email'],   # username 필드 필수 → email로 대체
            email=validated_data['email'],
            password=validated_data['password'],
            nickname=validated_data['nickname'],
        )
        return user


class LoginSerializer(serializers.Serializer):
    """
    로그인 유효성 검사 Serializer.
    email + password를 받아 Django authenticate()로 검증.
    유효하지 않으면 ValidationError 발생.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError('이메일 또는 비밀번호가 올바르지 않습니다.')
        if not user.is_active:
            raise serializers.ValidationError('비활성화된 계정입니다.')

        attrs['user'] = user
        return attrs


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    프로필 수정용 Serializer.
    nickname과 profile_img_url만 수정 허용.
    PUT /api/users/me/ 에 사용.
    """
    class Meta:
        model = User
        fields = ('nickname', 'profile_img_url')
