"""공개 배포 전 개인정보 마스킹.

data/ledger.json, data/index.json 의 문자열에서
전화번호·집 주소·계좌/로그인 아이디·본인 이메일·본인 이름을 중립 표기로 바꾼다.
`u`(바로가기 링크)와 `ids`(중복 체크 키)는 URL이 깨지지 않도록 이메일만 마스킹한다.
여러 번 돌려도 결과가 같도록(멱등) 작성했다.
"""
import json
import re

OWNER_EMAIL = re.compile(r'[\w.+-]*(?:ralehdwls|kdjkdj|dnccompany3|ubraindg)[\w.+-]*@[\w-]+\.[\w.]+')

TEXT_PATS = [
    # 휴대전화(가운데 자리 가림 표기 포함)
    (re.compile(r'01[016789]-\*{2,4}-\d{4}'), '[연락처]'),
    (re.compile(r'01[016789]-?\d{3,4}-?\d{4}'), '[연락처]'),
    # 본인 이메일
    (OWNER_EMAIL, '[이메일]'),
    # 본인 로그인 아이디
    (re.compile(r'\bralehdwls\w*'), '[아이디]'),
    (re.compile(r'\bkdjkdj\d+\b'), '[아이디]'),
    # 접수확인용 비밀번호(생년월일 4자리)
    (re.compile(r'(비밀번호\s*)[\d*]{4,8}'), r'\1[비밀번호]'),
    # 도로명 주소(우편번호 포함): 62225 풍영로170번길 39-25
    (re.compile(r'\d{5}\s*[가-힣]+(?:로|길)\s*\d+(?:번길)?\s*[\d-]+'), '[주소]'),
    (re.compile(r'[가-힣]{2,}(?:로|길)\d*(?:번길)?\s*\d+-\d+'), '[주소]'),
    # 동·호수
    (re.compile(r'\d{1,3}동\s*\d{1,4}호'), '[동호수]'),
    # 본인 이름
    (re.compile(r'김동진'), '본인'),
    (re.compile(r'동진\s*님'), '본인'),
]

LINK_PATS = [
    (OWNER_EMAIL, '[이메일]'),
]

TEXT_FIELDS = ('n', 't', 'g', 's', 'st', 'a', 'd', 'v', 'p', 'r', 'o')
LINK_FIELDS = ('u', 'ids')


def _apply(value, pats):
    if isinstance(value, str):
        for pat, rep in pats:
            value = pat.sub(rep, value)
        return value
    if isinstance(value, list):
        return [_apply(v, pats) for v in value]
    if isinstance(value, dict):
        return {k: _apply(v, pats) for k, v in value.items()}
    return value


def clean_item(item):
    out = dict(item)
    for k in list(out):
        if k in TEXT_FIELDS:
            out[k] = _apply(out[k], TEXT_PATS)
        elif k in LINK_FIELDS:
            out[k] = _apply(out[k], LINK_PATS)
        else:
            out[k] = _apply(out[k], TEXT_PATS + LINK_PATS)
    return out


def main():
    for path in ('data/ledger.json', 'data/index.json'):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        data['items'] = [clean_item(it) for it in data['items']]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        print(path, 'items:', len(data['items']))


if __name__ == '__main__':
    main()
