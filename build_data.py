import csv, json, re, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sanitize import clean_item  # 공개 배포용 개인정보 마스킹

INPUT_CSV = 'downloads/ledger_20261120.csv'
OUT_DIR = 'work/dongjin-event-hub/data'

def mask_sensitive(text):
    if not text:
        return ''
    # Mask phone numbers
    text = re.sub(r'01[016789]-?\d{3,4}-?\d{4}', '[연락처]', text)
    # Mask account numbers / long digits
    text = re.sub(r'\b\d{10,16}\b', '[계좌/번호]', text)
    # Mask addresses
    text = re.sub(r'(전남광주|전남|광주|전북|충남|서울)[^\s,/|)]{2,30}(동|면|읍|로|길|호)\s*\d*[-~]?\d*', '[주소]', text)
    text = re.sub(r'\d{2,4}동\s*\d{2,4}호', '[동호수]', text)
    return text

def extract_urls_and_ids(text):
    urls = re.findall(r'https?://[^\s,\)\]\'"]+', text or '')
    norm_ids = set()
    for u in urls:
        u_clean = u.rstrip('.,;')
        # Instagram
        m = re.search(r'instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)', u_clean)
        if m: norm_ids.add('ig:' + m.group(1))
        # YouTube
        m = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{6,})', u_clean)
        if m: norm_ids.add('yt:' + m.group(1))
        # Naver form / Google form
        m = re.search(r'(naver\.me/[A-Za-z0-9]+|forms\.gle/[A-Za-z0-9]+|docs\.google\.com/forms/d/e/[A-Za-z0-9_-]+)', u_clean)
        if m: norm_ids.add('form:' + m.group(1))
        # General host+path without query
        base = re.sub(r'\?.*$', '', u_clean).rstrip('/')
        if len(base) > 12:
            norm_ids.add('url:' + base.lower())
    return [u.rstrip('.,;') for u in urls], sorted(norm_ids)

def classify_group(row_title, cat, platform):
    t = f"{row_title} {cat} {platform}".lower()
    if any(k in t for k in ['공모전', '해커톤', '챌린지', '신춘문예', '아이디어', '시나리오', '백일장', '네이밍', '슬로건']):
        return '공모전'
    if any(k in t for k in ['체험단', '리뷰플레이스', '레뷰', '리뷰노트', '클라우드리뷰', '시딩', '무료체험']):
        return '체험단'
    return '이벤트'

items = []
seen_keys = set()

with open(INPUT_CSV, 'r', encoding='utf-8-sig', errors='replace') as f:
    reader = csv.DictReader(f)
    for row in reader:
        num = (row.get('번호') or '').strip()
        title = (row.get('이벤트명') or '').strip()
        ident = (row.get('이벤트 식별자') or '').strip()
        stage = (row.get('단계') or '').strip()
        applied_at = (row.get('응모일') or '').strip()
        deadline = (row.get('마감일') or '').strip()
        result = (row.get('결과/당첨') or '').strip()
        note = (row.get('증거/비고') or '').strip()
        cat = (row.get('카테고리(1인 경품 기준)') or '').strip()
        value = (row.get('1인당 경품가치') or '').strip()
        platform = (row.get('플랫폼/채널') or '').strip()
        res_state = (row.get('결과 상태') or '').strip()
        owner = (row.get('담당자(현재)') or '').strip()

        if not title and not ident:
            continue

        urls, norm_ids = extract_urls_and_ids(f"{ident} {note}")
        if ident and not ident.startswith('http') and len(ident) >= 4:
            norm_ids.append('id:' + ident.lower())
        norm_ids = sorted(set(norm_ids))

        # Status normalization
        status_norm = '기타'
        combined_res = f"{stage} {result} {res_state}"
        if '당첨' in combined_res or '선정' in combined_res:
            if '미당첨' not in combined_res and '미선정' not in combined_res and '낙선' not in combined_res:
                status_norm = '당첨'
        if status_norm != '당첨':
            if any(k in stage for k in ['완료', '접수', '제출', '부분완료']):
                status_norm = '응모완료'
            elif any(k in stage for k in ['안됨', '스킵', '제외', '불가', '중단']):
                status_norm = '제외'
            elif any(k in stage for k in ['발견', '대기', '보류', '확인']):
                status_norm = '대기'

        group = classify_group(title, cat, platform)

        # Numeric value estimate
        val_num = 0
        m_val = re.search(r'(\d[\d,]*)\s*만', value)
        if m_val:
            val_num = int(m_val.group(1).replace(',', '')) * 10000
        else:
            m_won = re.search(r'(\d[\d,]{3,})\s*원?', value)
            if m_won:
                val_num = int(m_won.group(1).replace(',', ''))

        items.append({
            'n': num,
            't': mask_sensitive(title),
            'g': group,
            's': status_norm,
            'st': mask_sensitive(stage),
            'a': applied_at,
            'd': deadline,
            'v': mask_sensitive(value),
            'vn': val_num,
            'p': mask_sensitive(platform),
            'r': mask_sensitive(result or res_state),
            'u': urls[0] if urls else '',
            'ids': norm_ids,
            'o': owner
        })

# Reverse so newest first
items.reverse()

# 공개 배포용 개인정보 마스킹(전화번호·주소·본인 이름·이메일·아이디)
items = [clean_item(x) for x in items]

with open(f'{OUT_DIR}/ledger.json', 'w', encoding='utf-8') as f:
    json.dump({'updated': '2026-11-20', 'total': len(items), 'items': items}, f, ensure_ascii=False)

# Lightweight AI index
index_items = [{'n': x['n'], 't': x['t'], 's': x['s'], 'd': x['d'], 'ids': x['ids']} for x in items]
with open(f'{OUT_DIR}/index.json', 'w', encoding='utf-8') as f:
    json.dump({'updated': '2026-11-20', 'total': len(index_items), 'items': index_items}, f, ensure_ascii=False)

print(f"Built {len(items)} items. Won: {sum(1 for x in items if x['s']=='당첨')}, Applied: {sum(1 for x in items if x['s']=='응모완료')}, Pending: {sum(1 for x in items if x['s']=='대기')}")
