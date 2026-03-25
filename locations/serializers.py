from rest_framework import serializers
from .models import AddressRegion, AddressDetail, Location


class LocationSerializer(serializers.ModelSerializer):
    """
    장소 읽기용 Serializer.
    Memory 생성/조회 시 location 필드에 중첩되어 사용.
    프론트가 필요한 핵심 필드만 노출.
    """
    # 중첩 주소 필드 플랫하게 노출
    road_address = serializers.CharField(
        source='address_detail.road_address_name', read_only=True
    )
    address = serializers.CharField(
        source='address_detail.address_name', read_only=True
    )

    class Meta:
        model = Location
        fields = ('id', 'kakao_place_id', 'place_name', 'road_address', 'address', 'latitude', 'longitude')


class LocationCreateSerializer(serializers.Serializer):
    """
    장소 생성 요청 Serializer.
    프론트에서 카카오 API 응답을 그대로 전달하면
    백엔드가 AddressRegion → AddressDetail → Location 순으로 정규화 저장.

    필수 필드:
      - place_name, latitude, longitude

    선택 필드 (카카오 장소 검색 결과가 있을 때):
      - kakao_place_id, province, city_district, town_neighborhood,
        road_address_name, address_name, main_address_no, sub_address_no
    """
    kakao_place_id    = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    place_name        = serializers.CharField()
    latitude          = serializers.FloatField()
    longitude         = serializers.FloatField()

    # 행정구역 (AddressRegion)
    province          = serializers.CharField(required=False, allow_blank=True, default='')
    city_district     = serializers.CharField(required=False, allow_blank=True, default='')
    town_neighborhood = serializers.CharField(required=False, allow_blank=True, default='')
    admin_town        = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    # 상세 주소 (AddressDetail)
    road_address_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address_name      = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    main_address_no   = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    sub_address_no    = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def create(self, validated_data):
        """
        1. kakao_place_id 있으면 기존 Location 반환 (중복 저장 방지)
        2. 없으면 AddressRegion → AddressDetail → Location 순서로 생성
        """
        kakao_place_id = validated_data.get('kakao_place_id') or None

        # 이미 저장된 장소면 그대로 반환
        if kakao_place_id:
            existing = Location.objects.filter(kakao_place_id=kakao_place_id).first()
            if existing:
                return existing

        # AddressRegion get_or_create (행정구역 마스터 중복 방지)
        region, _ = AddressRegion.objects.get_or_create(
            province=validated_data.get('province', ''),
            city_district=validated_data.get('city_district', ''),
            town_neighborhood=validated_data.get('town_neighborhood', ''),
            defaults={'admin_town': validated_data.get('admin_town')},
        )

        # AddressDetail get_or_create (상세주소 중복 방지)
        detail, _ = AddressDetail.objects.get_or_create(
            region=region,
            road_address_name=validated_data.get('road_address_name'),
            address_name=validated_data.get('address_name'),
            main_address_no=validated_data.get('main_address_no'),
            sub_address_no=validated_data.get('sub_address_no'),
        )

        # Location 생성
        location = Location.objects.create(
            kakao_place_id=kakao_place_id,
            address_detail=detail,
            place_name=validated_data['place_name'],
            latitude=validated_data['latitude'],
            longitude=validated_data['longitude'],
        )
        return location
