from django.contrib import admin
from .models import AddressRegion, AddressDetail, Location


@admin.register(AddressRegion)
class AddressRegionAdmin(admin.ModelAdmin):
    list_display = ('province', 'city_district', 'town_neighborhood', 'admin_town')
    list_filter = ('province', 'city_district')
    search_fields = ('province', 'city_district', 'town_neighborhood')
    ordering = ('province', 'city_district', 'town_neighborhood')


@admin.register(AddressDetail)
class AddressDetailAdmin(admin.ModelAdmin):
    list_display = ('road_address_name', 'address_name', 'region')
    search_fields = ('road_address_name', 'address_name')
    autocomplete_fields = ('region',)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('place_name', 'kakao_place_id', 'latitude', 'longitude', 'created_at')
    search_fields = ('place_name', 'kakao_place_id')
    autocomplete_fields = ('address_detail',)
