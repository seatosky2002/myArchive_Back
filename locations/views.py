from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Location
from .serializers import LocationCreateSerializer, LocationSerializer


class LocationCreateView(APIView):
    """
    POST /api/locations/
    카카오 API 응답 데이터를 받아 장소를 생성하거나 기존 장소를 반환.
    - kakao_place_id가 있으면 중복 저장 없이 기존 Location 반환.
    - 없으면 AddressRegion → AddressDetail → Location 순서로 정규화 저장.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = LocationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = serializer.save()
        return Response(LocationSerializer(location).data, status=status.HTTP_201_CREATED)


class LocationDetailView(APIView):
    """
    GET /api/locations/<id>/
    장소 상세 정보 조회 (place_name, 주소, 좌표).
    Memory 상세 보기에서 location 정보를 별도로 조회할 때 사용.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request, pk):
        try:
            location = Location.objects.select_related('address_detail__region').get(pk=pk)
        except Location.DoesNotExist:
            return Response({'detail': '장소를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(LocationSerializer(location).data)
