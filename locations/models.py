import uuid
from django.db import models


class AddressRegion(models.Model):
    """행정구역 마스터 (시/도, 시/군/구, 법정동/리)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    province = models.CharField(max_length=50, help_text='시/도 (ex: 서울특별시)')
    city_district = models.CharField(max_length=50, help_text='시/군/구 (ex: 강남구)')
    town_neighborhood = models.CharField(max_length=50, help_text='법정동/리 (ex: 역삼동)')
    admin_town = models.CharField(max_length=50, null=True, blank=True, help_text='행정동 (ex: 역삼1동)')

    class Meta:
        db_table = 'address_regions'
        constraints = [
            models.UniqueConstraint(
                fields=['province', 'city_district', 'town_neighborhood'],
                name='unique_region_idx',
            )
        ]

    def __str__(self):
        return f'{self.province} {self.city_district} {self.town_neighborhood}'


class AddressDetail(models.Model):
    """지번/도로명 상세 주소"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region = models.ForeignKey(
        AddressRegion,
        on_delete=models.PROTECT,
        related_name='address_details',
    )
    road_address_name = models.TextField(null=True, blank=True, help_text='도로명 주소 전체 (ex: 테헤란로 212)')
    address_name = models.TextField(null=True, blank=True, help_text='지번 주소 전체 (ex: 역삼동 642-1)')
    main_address_no = models.CharField(max_length=20, null=True, blank=True, help_text='본번 (ex: 642)')
    sub_address_no = models.CharField(max_length=20, null=True, blank=True, help_text='부번 (ex: 1)')

    class Meta:
        db_table = 'address_details'
        constraints = [
            models.UniqueConstraint(
                fields=['region', 'road_address_name', 'address_name', 'main_address_no', 'sub_address_no'],
                name='unique_detail_address_idx',
            )
        ]

    def __str__(self):
        return self.road_address_name or self.address_name or str(self.id)


class Location(models.Model):
    """최종 POI (카카오 장소)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kakao_place_id = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text='카카오 맵 고유 ID (지도 직접 클릭 시 null)',
    )
    address_detail = models.ForeignKey(
        AddressDetail,
        on_delete=models.PROTECT,
        related_name='locations',
    )
    place_name = models.CharField(max_length=100, help_text='장소명 (ex: 멀티캠퍼스 역삼)')
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'locations'

    def __str__(self):
        return self.place_name
