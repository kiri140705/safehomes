# -*- coding: utf-8 -*-
"""
카카오 로그인(OAuth) 기반 실제 알림 발송 모듈.

기존 background_scanner.py는 새 매물을 찾아도 콘솔에 print하고 로컬 텍스트 파일에
적기만 할 뿐, 사용자의 카카오톡에는 아무것도 보내지 않는 "모의 발송"이었다.
이 모듈은 카카오 로그인으로 사용자별 액세스 토큰을 발급받아 실제로
"나에게 보내기(memo API)"를 호출해서 진짜 알림을 보낸다.

필요한 사전 설정 (카카오 디벨로퍼스 콘솔):
1. [내 애플리케이션] > [카카오 로그인] 활성화
2. [카카오 로그인] > Redirect URI에 KAKAO_REDIRECT_URI(.env)와 동일한 값 등록
3. [카카오 로그인] > 동의항목에서 "카카오톡 메시지 전송(talk_message)" 활성화
   (친구/알림톡과 달리 "나에게 보내기"는 별도의 비즈니스 심사 없이 사용 가능하다)
"""
import os
import json
import datetime
import requests
import urllib.parse
from dotenv import load_dotenv

from notification_db import save_kakao_token, get_kakao_token

load_dotenv()

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET") or None
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def get_kakao_authorize_url(user_id: str) -> str:
    """유저가 딱 한 번 눌러서 카카오 로그인 동의하면 실제 알림 수신이 활성화되는 링크를 만든다.
    user_id를 state 파라미터로 실어 보내서, 콜백에서 어느 유저의 알림에 연결할지 식별한다."""
    if not KAKAO_REST_API_KEY or not KAKAO_REDIRECT_URI:
        return None
    params = {
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "response_type": "code",
        "scope": "talk_message",
        "state": user_id or "고객",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
    """OAuth 인가 코드를 실제 액세스/리프레시 토큰으로 교환한다."""
    data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
    }
    if KAKAO_CLIENT_SECRET:
        data["client_secret"] = KAKAO_CLIENT_SECRET

    res = requests.post(TOKEN_URL, data=data, timeout=5)
    res.raise_for_status()
    return res.json()


def has_talk_message_scope(access_token: str) -> bool:
    """talk_message는 [선택 동의] 항목이라, 로그인 자체는 성공해도 사용자가 이 항목만
    체크 해제했을 수 있다. 발급된 토큰에 실제로 이 권한이 포함됐는지 확인한다."""
    try:
        res = requests.get(
            "https://kapi.kakao.com/v2/user/scopes",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
        if res.status_code != 200:
            return False
        scopes = res.json().get("scopes", [])
        return any(s.get("id") == "talk_message" and s.get("agreed") for s in scopes)
    except Exception as e:
        print(f"[!] 카카오 동의 항목 확인 실패: {e}")
        return False


def _refresh_access_token(refresh_token: str) -> dict:
    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": refresh_token,
    }
    if KAKAO_CLIENT_SECRET:
        data["client_secret"] = KAKAO_CLIENT_SECRET

    res = requests.post(TOKEN_URL, data=data, timeout=5)
    res.raise_for_status()
    return res.json()


def _get_valid_access_token(user_id: str) -> str:
    """저장된 토큰을 확인하고, 만료됐으면 자동 갱신한 뒤 유효한 access_token을 반환한다.
    연동된 적이 없으면 None."""
    token_row = get_kakao_token(user_id)
    if not token_row:
        return None

    expires_at = token_row.get("expires_at")
    is_expired = True
    if expires_at:
        try:
            is_expired = datetime.datetime.fromisoformat(expires_at) <= datetime.datetime.now()
        except ValueError:
            is_expired = True

    if not is_expired:
        return token_row["access_token"]

    if not token_row.get("refresh_token"):
        return None

    try:
        refreshed = _refresh_access_token(token_row["refresh_token"])
    except Exception as e:
        print(f"[!] 카카오 토큰 갱신 실패({user_id}): {e}")
        return None

    new_access = refreshed.get("access_token")
    new_refresh = refreshed.get("refresh_token") or token_row["refresh_token"]
    expires_in = refreshed.get("expires_in", 21599)
    new_expires_at = (datetime.datetime.now() + datetime.timedelta(seconds=expires_in)).isoformat()
    save_kakao_token(user_id, new_access, new_refresh, new_expires_at)
    return new_access


def is_kakao_linked(user_id: str) -> bool:
    return get_kakao_token(user_id) is not None


def send_kakao_memo(user_id: str, title: str, description: str, link_url: str = None) -> bool:
    """카카오 '나에게 보내기' API로 실제 알림을 발송한다. 연동 안 돼있거나 실패하면 False."""
    access_token = _get_valid_access_token(user_id)
    if not access_token:
        return False

    template_object = {
        "object_type": "text",
        "text": f"{title}\n\n{description}"[:200],
        "link": {
            "web_url": link_url or "https://www.applyhome.co.kr",
            "mobile_web_url": link_url or "https://www.applyhome.co.kr",
        },
        "button_title": "바로 확인하기",
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    data = {"template_object": json.dumps(template_object, ensure_ascii=False)}

    try:
        res = requests.post(MEMO_SEND_URL, headers=headers, data=data, timeout=5)
        if res.status_code == 200:
            return True
        print(f"[!] 카카오 알림 발송 실패({user_id}): {res.status_code} {res.text}")
        return False
    except Exception as e:
        print(f"[!] 카카오 알림 발송 예외({user_id}): {e}")
        return False
