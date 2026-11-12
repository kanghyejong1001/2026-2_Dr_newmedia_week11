"""learning_history 를 근거로 로그인 시 게임 메뉴 순서를 재배치 (11주차 기능 4).

기본 정책(ORDER_STRATEGY)
------------------------
"dwell_desc" : 누적 체류 시간이 긴 게임 메뉴를 위로.
               → 가장 오래 머문(=몰입한) 메뉴를 먼저 노출.
바꾸고 싶으면 ORDER_STRATEGY 값만 수정하면 된다.
  - "recent"    : 최근에 본 메뉴 우선
  - "freq_desc" : 방문 횟수가 많은 메뉴 우선
  - "dwell_asc" : 체류가 짧은(=아직 손대지 않은) 메뉴 우선
방문 이력이 없는 게임은 항상 원래 순서(pythonid → 블록리 → 테트리스)를 유지한 채 뒤에 붙는다.
"""
from database import get_db_connection

DEFAULT_GAME_MENUS = ("pythonid", "블록리게임", "테트리스게임")
ORDER_STRATEGY = "dwell_desc"

STRATEGY_LABELS = {
    "dwell_desc": "누적 체류 시간 많은 순",
    "dwell_asc": "누적 체류 시간 적은 순",
    "recent": "최근 방문 순",
    "freq_desc": "방문 횟수 많은 순",
}


def ordered_game_menus(user_id: str, menus=DEFAULT_GAME_MENUS, strategy: str = ORDER_STRATEGY) -> list:
    """로그인 직후 호출해 사이드바 라디오 버튼 순서를 결정한다."""
    menus = list(menus)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT menu_id, SUM(waiting_time) AS total, COUNT(*) AS visits, "
        "MAX(created_at) AS last_seen FROM learning_history WHERE user_id = ? GROUP BY menu_id",
        (user_id,),
    )
    stats = {r[0]: {"total": float(r[1] or 0.0), "visits": int(r[2] or 0), "last_seen": r[3] or ""}
             for r in c.fetchall()}
    conn.close()

    index = {m: i for i, m in enumerate(menus)}

    def value(m):
        return stats.get(m) or {"total": 0.0, "visits": 0, "last_seen": ""}

    if strategy == "dwell_desc":
        return sorted(menus, key=lambda m: (-value(m)["total"], -value(m)["visits"], index[m]))
    if strategy == "dwell_asc":
        return sorted(menus, key=lambda m: (value(m)["total"], -value(m)["visits"], index[m]))
    if strategy == "freq_desc":
        return sorted(menus, key=lambda m: (-value(m)["visits"], -value(m)["total"], index[m]))

    # recent: 최근 방문 순 (동률은 원래 순서 유지)
    ordered = sorted(menus, key=lambda m: index[m])
    ordered.sort(key=lambda m: (value(m)["last_seen"], value(m)["total"]), reverse=True)
    return ordered
