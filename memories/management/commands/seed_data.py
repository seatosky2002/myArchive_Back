"""
seed_data.py — 서울대입구역 주변 샘플 데이터 500개 생성

사용법:
    python manage.py seed_data
    python manage.py seed_data --count 200   # 개수 지정
    python manage.py seed_data --email user@test.com  # 특정 유저로 생성
    python manage.py seed_data --clear       # 기존 데이터 삭제 후 재생성

생성 데이터:
    - 서울 관악구(서울대입구역, 샤로수길 일대) 장소 약 60곳
    - 식사 / 카페 / 영화 / 데이트 / 피시방 / 공부 / 술 / 운동 / 혼밥 카테고리
    - 날짜: 2026-01-01 ~ 2026-03-25
    - 무드 / 날씨 랜덤 조합
"""

import random
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from locations.models import AddressRegion, AddressDetail, Location
from memories.models import Category, Memory, MemoryDetail, Tag

User = get_user_model()

# ───────────────────────────────────────────
# 서울대입구 / 샤로수길 주변 장소 데이터
# ───────────────────────────────────────────
PLACES = [
    # ── 카페 ──────────────────────────────
    {"name": "블루보틀 샤로수길점",       "category": "카페",  "lat": 37.4815, "lng": 126.9528, "tags": ["카페", "커피", "샤로수길"]},
    {"name": "어니언 관악점",             "category": "카페",  "lat": 37.4808, "lng": 126.9522, "tags": ["카페", "브런치", "감성"]},
    {"name": "테라로사 서울대입구점",      "category": "카페",  "lat": 37.4820, "lng": 126.9535, "tags": ["카페", "스페셜티", "조용한"]},
    {"name": "폴바셋 관악점",             "category": "카페",  "lat": 37.4802, "lng": 126.9519, "tags": ["카페", "디저트"]},
    {"name": "카페 봄봄",                 "category": "카페",  "lat": 37.4795, "lng": 126.9510, "tags": ["카페", "아늑한", "공부"]},
    {"name": "루소 커피",                 "category": "카페",  "lat": 37.4788, "lng": 126.9505, "tags": ["커피", "혼자", "공부카페"]},
    {"name": "딜쿠샤 샤로수길",           "category": "카페",  "lat": 37.4811, "lng": 126.9530, "tags": ["카페", "감성", "데이트"]},
    {"name": "오우 커피로스터스",          "category": "카페",  "lat": 37.4825, "lng": 126.9540, "tags": ["스페셜티", "커피"]},
    {"name": "카페 드 파리",              "category": "카페",  "lat": 37.4799, "lng": 126.9515, "tags": ["카페", "프렌치", "여유"]},
    {"name": "북카페 페이지원",           "category": "카페",  "lat": 37.4793, "lng": 126.9508, "tags": ["북카페", "독서", "조용한"]},

    # ── 식사 ──────────────────────────────
    {"name": "봉천동 순대국",             "category": "식사",  "lat": 37.4835, "lng": 126.9545, "tags": ["순대국", "해장", "혼밥"]},
    {"name": "관악 부대찌개",             "category": "식사",  "lat": 37.4790, "lng": 126.9500, "tags": ["부대찌개", "찌개", "밥"]},
    {"name": "샤로수길 파스타",           "category": "식사",  "lat": 37.4807, "lng": 126.9525, "tags": ["파스타", "이탈리안", "데이트"]},
    {"name": "옛날 왕족발",               "category": "식사",  "lat": 37.4840, "lng": 126.9550, "tags": ["족발", "배달", "야식"]},
    {"name": "관악 초밥집",              "category": "식사",  "lat": 37.4785, "lng": 126.9498, "tags": ["초밥", "일식", "데이트"]},
    {"name": "서울대입구 육쌈냉면",       "category": "식사",  "lat": 37.4818, "lng": 126.9532, "tags": ["냉면", "여름", "점심"]},
    {"name": "명동칼국수 관악점",         "category": "식사",  "lat": 37.4828, "lng": 126.9542, "tags": ["칼국수", "점심", "국물"]},
    {"name": "샤로수길 마라탕",           "category": "식사",  "lat": 37.4804, "lng": 126.9520, "tags": ["마라탕", "중식", "매운"]},
    {"name": "봉천동 곱창",              "category": "식사",  "lat": 37.4845, "lng": 126.9555, "tags": ["곱창", "술안주", "야식"]},
    {"name": "스시 오마카세 칸",          "category": "식사",  "lat": 37.4796, "lng": 126.9512, "tags": ["오마카세", "스시", "특별한날"]},
    {"name": "관악 감자탕",              "category": "식사",  "lat": 37.4838, "lng": 126.9548, "tags": ["감자탕", "해장", "술다음날"]},
    {"name": "봉천 삼겹살 거리",          "category": "식사",  "lat": 37.4850, "lng": 126.9558, "tags": ["삼겹살", "고기", "친구"]},
    {"name": "타이 레스토랑 쏨땀",        "category": "식사",  "lat": 37.4810, "lng": 126.9527, "tags": ["태국음식", "팟타이", "이색적인"]},
    {"name": "관악 육개장 칼국수",        "category": "식사",  "lat": 37.4822, "lng": 126.9537, "tags": ["육개장", "칼국수", "점심"]},
    {"name": "피자 알볼로 관악점",        "category": "식사",  "lat": 37.4800, "lng": 126.9517, "tags": ["피자", "혼밥", "배달"]},

    # ── 피시방 ────────────────────────────
    {"name": "게임존 PC방 서울대입구점",   "category": "피시방", "lat": 37.4832, "lng": 126.9544, "tags": ["PC방", "게임", "밤샘"]},
    {"name": "아이온 PC방",              "category": "피시방", "lat": 37.4843, "lng": 126.9553, "tags": ["PC방", "롤", "친구"]},
    {"name": "넥스트 PC클럽",            "category": "피시방", "lat": 37.4826, "lng": 126.9541, "tags": ["PC방", "배그", "스트레스해소"]},
    {"name": "탑건 PC방",               "category": "피시방", "lat": 37.4837, "lng": 126.9547, "tags": ["PC방", "게임", "야밤"]},
    {"name": "스타PC방 관악점",           "category": "피시방", "lat": 37.4819, "lng": 126.9533, "tags": ["PC방", "스타크래프트", "추억"]},

    # ── 영화 ──────────────────────────────
    {"name": "CGV 관악",                 "category": "영화",  "lat": 37.4784, "lng": 126.9495, "tags": ["영화", "CGV", "데이트"]},
    {"name": "롯데시네마 관악점",          "category": "영화",  "lat": 37.4778, "lng": 126.9488, "tags": ["영화", "팝콘", "주말"]},
    {"name": "씨네큐 서울대입구",          "category": "영화",  "lat": 37.4791, "lng": 126.9503, "tags": ["영화", "인디", "예술영화"]},

    # ── 데이트 ────────────────────────────
    {"name": "관악산 등산로 입구",         "category": "데이트", "lat": 37.4755, "lng": 126.9628, "tags": ["등산", "자연", "데이트"]},
    {"name": "서울대 캠퍼스 산책로",       "category": "데이트", "lat": 37.4602, "lng": 126.9525, "tags": ["산책", "캠퍼스", "데이트"]},
    {"name": "샤로수길 포토존",           "category": "데이트", "lat": 37.4813, "lng": 126.9529, "tags": ["사진", "인스타", "데이트"]},
    {"name": "낙성대 공원",              "category": "데이트", "lat": 37.4763, "lng": 126.9632, "tags": ["공원", "산책", "여유"]},
    {"name": "봉천천 산책로",             "category": "데이트", "lat": 37.4855, "lng": 126.9488, "tags": ["산책", "자연", "조용한"]},
    {"name": "관악 보드게임 카페",         "category": "데이트", "lat": 37.4806, "lng": 126.9523, "tags": ["보드게임", "실내", "재미있는"]},
    {"name": "방탈출 카페 이스케이프",     "category": "데이트", "lat": 37.4801, "lng": 126.9518, "tags": ["방탈출", "스릴", "데이트"]},

    # ── 술 ────────────────────────────────
    {"name": "봉천동 포장마차",           "category": "술",    "lat": 37.4848, "lng": 126.9556, "tags": ["포장마차", "소주", "야식"]},
    {"name": "샤로수길 와인바",           "category": "술",    "lat": 37.4809, "lng": 126.9526, "tags": ["와인", "분위기", "데이트"]},
    {"name": "관악 수제맥주 펍",          "category": "술",    "lat": 37.4797, "lng": 126.9513, "tags": ["맥주", "펍", "친구"]},
    {"name": "봉천 막걸리집",             "category": "술",    "lat": 37.4842, "lng": 126.9552, "tags": ["막걸리", "전통주", "파전"]},
    {"name": "이자카야 칸파이",           "category": "술",    "lat": 37.4816, "lng": 126.9531, "tags": ["이자카야", "일본식", "하이볼"]},

    # ── 공부 ──────────────────────────────
    {"name": "관악 스터디카페 1호점",      "category": "공부",  "lat": 37.4829, "lng": 126.9543, "tags": ["스터디카페", "공부", "조용한"]},
    {"name": "서울대 중앙도서관",         "category": "공부",  "lat": 37.4611, "lng": 126.9527, "tags": ["도서관", "공부", "서울대"]},
    {"name": "봉천 독서실",              "category": "공부",  "lat": 37.4844, "lng": 126.9554, "tags": ["독서실", "집중", "시험"]},
    {"name": "관악 스터디룸 24",          "category": "공부",  "lat": 37.4821, "lng": 126.9536, "tags": ["스터디룸", "그룹공부", "발표준비"]},

    # ── 쇼핑 ──────────────────────────────
    {"name": "관악 현대백화점",           "category": "쇼핑",  "lat": 37.4779, "lng": 126.9490, "tags": ["쇼핑", "백화점", "쇼핑몰"]},
    {"name": "봉천동 올리브영",           "category": "쇼핑",  "lat": 37.4831, "lng": 126.9543, "tags": ["올리브영", "화장품", "쇼핑"]},
    {"name": "샤로수길 빈티지샵",         "category": "쇼핑",  "lat": 37.4812, "lng": 126.9528, "tags": ["빈티지", "옷", "샤로수길"]},
    {"name": "관악 다이소",              "category": "쇼핑",  "lat": 37.4827, "lng": 126.9541, "tags": ["다이소", "생활용품", "쇼핑"]},

    # ── 운동 ──────────────────────────────
    {"name": "관악구민 수영장",           "category": "운동",  "lat": 37.4762, "lng": 126.9508, "tags": ["수영", "운동", "건강"]},
    {"name": "관악 헬스클럽",            "category": "운동",  "lat": 37.4835, "lng": 126.9546, "tags": ["헬스", "운동", "다이어트"]},
    {"name": "관악산 둘레길",             "category": "운동",  "lat": 37.4750, "lng": 126.9640, "tags": ["등산", "둘레길", "산책"]},
    {"name": "봉천 클라이밍 센터",        "category": "운동",  "lat": 37.4846, "lng": 126.9557, "tags": ["클라이밍", "운동", "취미"]},

    # ── 혼밥 ──────────────────────────────
    {"name": "서울대입구 편의점 CU",      "category": "혼밥",  "lat": 37.4817, "lng": 126.9532, "tags": ["편의점", "혼밥", "간단한"]},
    {"name": "봉천동 혼밥 국수집",        "category": "혼밥",  "lat": 37.4839, "lng": 126.9549, "tags": ["국수", "혼밥", "점심"]},
    {"name": "관악 덮밥 전문점",          "category": "혼밥",  "lat": 37.4824, "lng": 126.9539, "tags": ["덮밥", "혼밥", "빠른식사"]},
    {"name": "샤로수길 1인 라멘집",       "category": "혼밥",  "lat": 37.4806, "lng": 126.9524, "tags": ["라멘", "혼밥", "일식"]},
]

# ───────────────────────────────────────────
# 기록 본문 템플릿 (카테고리별)
# ───────────────────────────────────────────
CONTENTS = {
    "카페": [
        "오늘도 여기 왔다. 창가 자리 잡고 아메리카노 한 잔. 밖에 지나가는 사람들 구경하다 보면 시간이 잘 간다.",
        "스페셜티 원두 향이 정말 좋다. 드립 커피 마시면서 책 한 권 읽었더니 기분이 한결 나아졌다.",
        "친구랑 수다 떨다가 결국 세 시간 넘게 있었다. 케이크도 맛있었고 분위기도 딱이었다.",
        "공부하러 왔는데 너무 편해서 그냥 멍 때리다 나왔다. 그것도 나름 충전이지.",
        "비 오는 날 카페에 있으면 왜 이렇게 감성 충만해지는 건지. 창밖 빗소리 들으며 커피 한 잔.",
        "오늘 처음 와봤는데 분위기가 너무 좋다. 단골이 될 것 같은 예감.",
    ],
    "식사": [
        "배고플 때 생각나는 그 맛. 국물이 진하고 깊어서 먹고 나면 든든하다.",
        "오늘 점심은 여기! 혼자 왔는데 직원분이 친절해서 좋았다. 다음에 또 와야지.",
        "친구랑 오랜만에 만나서 실컷 먹었다. 음식보다 수다가 더 맛있었을지도.",
        "처음 먹어봤는데 생각보다 훨씬 맛있다. 이게 왜 유명한지 알겠다.",
        "늦은 점심이라 한산해서 좋았다. 조용히 혼자 먹는 시간도 나쁘지 않다.",
        "시험 끝나고 왔더니 뭘 먹어도 맛있다. 오늘은 배부르게 먹어도 돼.",
        "날이 추워서 뜨끈한 국물이 당겼다. 역시 이럴 때는 이게 최고다.",
    ],
    "피시방": [
        "오늘 완전 집중해서 했더니 랭크 한 등 올랐다. 뿌듯.",
        "친구들이랑 새벽까지 했다. 내일 후회할 거 알면서도 멈출 수가 없었다.",
        "스트레스 풀려고 왔는데 지니까 오히려 더 쌓였다. 이게 PC방의 함정이다.",
        "오랜만에 왔는데 사양이 좋아져서 쾌적했다. 게임하면서 시간 가는 줄 몰랐다.",
        "밥 먹고 소화시킬 겸 왔다. 한두 판만 하려다 결국 세 시간.",
    ],
    "영화": [
        "예고편보다 훨씬 재밌었다. 중간에 몇 번 울기도 했고. 오길 잘했다.",
        "혼자 보는 영화도 나쁘지 않다. 오히려 집중이 더 잘 됐다.",
        "데이트 코스로 딱이었다. 영화 보고 나서 내용 얘기하면서 밥 먹으러 갔다.",
        "솔직히 기대치가 낮았는데 생각보다 훨씬 좋았다. 감독 전작 찾아봐야겠다.",
        "팝콘 양이 너무 많아서 다 못 먹었다. 영화는 무난무난.",
    ],
    "데이트": [
        "오랜만에 여유로운 하루. 목적지 없이 걷다 보니 여기까지 왔다.",
        "날씨가 딱 좋아서 산책하기 최고였다. 이런 날이 또 있으면 좋겠다.",
        "처음 와보는 곳인데 분위기가 너무 좋다. 다음에 또 오고 싶다.",
        "오늘 하루 완전 충전됐다. 같이 있으면 시간이 왜 이렇게 빨리 가는 건지.",
        "별거 아닌 것도 재밌었다. 그냥 같이라서 좋은 것 같다.",
    ],
    "술": [
        "오늘 진짜 힘든 하루였는데 한 잔 하니까 풀리는 기분이다.",
        "친구들이랑 새벽까지 마셨다. 내일 분명히 후회할 텐데 오늘은 그냥.",
        "분위기 좋은 곳에서 와인 한 잔. 조용히 이야기 나누다 보니 시간이 훌쩍.",
        "포장마차에서 먹는 어묵국물이 제일 맛있다. 소주 한 잔에 뭔가 위로가 됐다.",
        "수제맥주 종류가 다양해서 골라 먹는 재미가 있다. 다 맛있었음.",
    ],
    "공부": [
        "오늘은 생각보다 집중이 잘 됐다. 목표치 달성하고 나오니 뿌듯하다.",
        "시험 기간이라 하루 종일 여기 있었다. 힘들지만 다 잘 될 거라 믿는다.",
        "카페보다 여기가 집중이 잘 된다. 조용한 게 역시 최고.",
        "오늘 진도가 잘 안 나갔다. 그냥 자리 지키는 것도 의미 있다고 생각하자.",
        "스터디 모임이 있어서 왔다. 같이 하니까 확실히 효율이 다르다.",
    ],
    "쇼핑": [
        "사려던 건 없었는데 구경하다 보니 이것저것 담게 됐다.",
        "오늘 쇼핑 완전 성공. 고민하던 걸 드디어 샀다. 기분 좋다.",
        "그냥 눈팅만 하려다가 결국 지갑을 열었다. 후회는 없다.",
        "세일 기간이라 사람이 많았다. 그래도 원하는 거 다 건졌다.",
    ],
    "운동": [
        "오늘 운동 드디어 했다. 안 하던 사람이 하니까 힘들긴 한데 개운하다.",
        "꾸준히 나오는 게 제일 중요하다. 오늘도 완료.",
        "생각보다 훨씬 힘들었다. 근데 끝나고 나면 이 기분이 좋아서 계속 오게 된다.",
        "운동하고 나서 먹는 밥이 제일 맛있다. 오늘 저녁 기대된다.",
    ],
    "혼밥": [
        "혼자 밥 먹는 게 이제 전혀 어색하지 않다. 오히려 여유롭고 좋다.",
        "빠르게 먹고 다음 일정으로. 효율적인 점심이었다.",
        "혼밥할 때 제일 중요한 건 휴대폰. 영상 보면서 먹었더니 금방 먹었다.",
        "가게가 한산해서 천천히 먹을 수 있었다. 이런 여유가 좋다.",
    ],
}

MOODS = ['peaceful', 'happy', 'calm', 'energetic', 'sad', 'excited']
WEATHERS = ['sunny', 'cloudy', 'rainy', 'snowy', 'night', 'sunrise']

# 날씨 계절 가중치 (1~3월)
WEATHER_WEIGHTS_BY_MONTH = {
    1: [0.15, 0.25, 0.10, 0.30, 0.15, 0.05],  # 겨울: 눈/흐림 많음
    2: [0.15, 0.25, 0.10, 0.25, 0.15, 0.10],  # 겨울 끝
    3: [0.30, 0.25, 0.15, 0.10, 0.10, 0.10],  # 봄: 맑음 늘어남
}


class Command(BaseCommand):
    help = '서울대입구역 주변 샘플 데이터 생성'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=500, help='생성할 기록 수')
        parser.add_argument('--email', type=str, default='test@mymemorymap.com', help='사용자 이메일')
        parser.add_argument('--clear', action='store_true', help='기존 데이터 삭제 후 재생성')

    def handle(self, *args, **options):
        count = options['count']
        email = options['email']

        if options['clear']:
            self.stdout.write('기존 데이터 삭제 중...')
            Memory.objects.filter(user__email=email).delete()
            self.stdout.write(self.style.WARNING('기존 기록 삭제 완료'))

        # 1. 유저 생성 or 조회
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email,
                'nickname': '테스트 유저',
                'is_active': True,
            }
        )
        if created:
            user.set_password('test1234!')
            user.save()
            self.stdout.write(self.style.SUCCESS(f'유저 생성: {email}'))
        else:
            self.stdout.write(f'기존 유저 사용: {email}')

        # 2. 카테고리 생성
        category_colors = {
            '카페': '#A78BFA', '식사': '#F97316', '피시방': '#6366F1',
            '영화': '#EC4899', '데이트': '#F43F5E', '술': '#8B5CF6',
            '공부': '#3B82F6', '쇼핑': '#10B981', '운동': '#EF4444', '혼밥': '#F59E0B',
        }
        categories = {}
        for name, color in category_colors.items():
            cat, _ = Category.objects.get_or_create(user=user, name=name, defaults={'color_code': color})
            categories[name] = cat
        self.stdout.write(f'카테고리 {len(categories)}개 준비 완료')

        # 3. 주소 마스터 생성
        region, _ = AddressRegion.objects.get_or_create(
            province='서울특별시',
            city_district='관악구',
            town_neighborhood='봉천동',
        )

        detail, _ = AddressDetail.objects.get_or_create(
            region=region,
            road_address_name='서울특별시 관악구 봉천로',
            address_name='서울특별시 관악구 봉천동',
            main_address_no='',
            sub_address_no='',
        )

        # 4. 장소 생성 or 조회
        location_objs = {}
        for p in PLACES:
            loc, _ = Location.objects.get_or_create(
                place_name=p['name'],
                defaults={
                    'kakao_place_id': None,
                    'address_detail': detail,
                    'latitude': p['lat'] + random.uniform(-0.0003, 0.0003),
                    'longitude': p['lng'] + random.uniform(-0.0003, 0.0003),
                }
            )
            location_objs[p['name']] = (loc, p)
        self.stdout.write(f'장소 {len(location_objs)}개 준비 완료')

        # 5. 날짜 범위 생성 (2026-01-01 ~ 2026-03-25)
        start = date(2026, 1, 1)
        end = date(2026, 3, 25)
        date_range = [start + timedelta(days=i) for i in range((end - start).days + 1)]

        # 6. 기록 500개 생성
        self.stdout.write(f'{count}개 기록 생성 시작...')
        created_count = 0

        with transaction.atomic():
            for _ in range(count):
                place_data = random.choice(PLACES)
                loc_obj, p = location_objs[place_data['name']]
                cat_name = p['category']
                cat_obj = categories[cat_name]
                visited = random.choice(date_range)
                mood = random.choice(MOODS)
                weather_weights = WEATHER_WEIGHTS_BY_MONTH[visited.month]
                weather = random.choices(WEATHERS, weights=weather_weights)[0]
                content_list = CONTENTS.get(cat_name, CONTENTS['식사'])
                content = random.choice(content_list)
                tags = p['tags'][:]
                # 추가 태그 랜덤 1~2개
                extra_tags = ['기록', '서울대입구', '관악구', '일상', '샤로수길', '봉천동', '추억']
                tags += random.sample(extra_tags, k=random.randint(0, 2))

                memory = Memory.objects.create(
                    user=user,
                    location=loc_obj,
                    category=cat_obj,
                    title=self._make_title(cat_name, place_data['name'], visited),
                    mood=mood,
                    weather=weather,
                    visited_at=visited,
                )
                MemoryDetail.objects.create(memory=memory, content=content)
                Tag.objects.bulk_create(
                    [Tag(memory=memory, name=t) for t in set(tags)],
                    ignore_conflicts=True,
                )
                created_count += 1

                if created_count % 50 == 0:
                    self.stdout.write(f'  {created_count}/{count} 생성 중...')

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ 완료! {created_count}개 기록 생성됨\n'
            f'   유저: {email}\n'
            f'   비밀번호: test1234!\n'
            f'   기간: 2026-01-01 ~ 2026-03-25'
        ))

    def _make_title(self, category, place_name, visited):
        """카테고리와 날짜 기반으로 자연스러운 제목 생성"""
        templates = {
            '카페':   [f"{place_name}에서 커피 한 잔", f"카페 {place_name}", f"{visited.month}월의 카페 타임"],
            '식사':   [f"{place_name} 점심", f"{place_name} 방문", f"{visited.month}월의 맛집"],
            '피시방': [f"{place_name}에서 게임", f"밤새 게임한 날", f"{place_name} 습격"],
            '영화':   [f"영화 보러 간 날", f"{place_name} 영화 관람", f"스크린 앞에서"],
            '데이트': [f"{place_name} 데이트", f"좋은 사람과 {place_name}", f"{visited.month}월 나들이"],
            '술':     [f"{place_name}에서 한 잔", f"오늘은 한 잔 해야 해", f"{visited.month}월 밤"],
            '공부':   [f"{place_name} 공부 모드", f"오늘의 공부 장소", f"집중력 충전 완료"],
            '쇼핑':   [f"{place_name} 쇼핑", f"지갑이 얇아진 날", f"{visited.month}월 쇼핑"],
            '운동':   [f"{place_name} 운동 완료", f"오늘의 운동", f"몸이 좋아지는 중"],
            '혼밥':   [f"{place_name} 혼밥", f"혼자만의 점심", f"나만의 식사 시간"],
        }
        return random.choice(templates.get(category, [place_name]))
