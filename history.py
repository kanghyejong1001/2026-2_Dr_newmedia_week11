"""학습 이력(learning_history) 기록 모듈 (11주차 기능 이식).

기록 방식
---------
1) 게임 메뉴를 클릭하는 순간 start_visit() 이 waiting_time=0 행을 INSERT 한다.
   (클릭 즉시 이력이 남으므로, 브라우저를 그냥 닫아도 행이 유실되지 않는다)
2) 다른 메뉴로 전환하거나 로그아웃하는 순간 finish_visit() 이 체류 시간(초)을 UPDATE 한다.
"""
import time
from datetime import datetime, timezone

from database import get_db_connection


def now_iso() -> str:
    """한국 시각(KST) ISO8601 문자열."""
    from datetime import timedelta
    kst = datetime.now(timezone(timedelta(hours=9)))
    return kst.isoformat(timespec="seconds")


def start_visit(user_id: str, menu_id: str):
    """메뉴 클릭 시 호출. (history_id, 체류 측정 시작 시각) 반환."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO learning_history (user_id, menu_id, waiting_time, created_at) "
        "VALUES (?, ?, 0, ?)",
        (user_id, menu_id, now_iso()),
    )
    conn.commit()
    visit_id = c.lastrowid
    conn.close()
    return int(visit_id), time.time()


def finish_visit(visit_id, started_at) -> float:
    """다른 메뉴로 이동/로그아웃 시 호출. 확정된 체류 시간(초)을 반환."""
    if not visit_id or started_at is None:
        return 0.0
    elapsed = max(0.0, round(time.time() - started_at, 1))
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE learning_history SET waiting_time = ? WHERE id = ?", (elapsed, visit_id))
    conn.commit()
    conn.close()
    return elapsed


def recent_visits(user_id: str, menu_id: str, limit: int = 10):
    """특정 메뉴의 최근 체류 기록."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, menu_id, waiting_time, created_at FROM learning_history "
        "WHERE user_id = ? AND menu_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, menu_id, limit),
    )
    rows = [dict(zip(["id", "menu_id", "waiting_time", "created_at"], r)) for r in c.fetchall()]
    conn.close()
    return rows


def menu_stats(user_id: str) -> dict:
    """메뉴별 누적 체류 시간 / 방문 횟수 / 최근 방문 시각."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT menu_id, SUM(waiting_time) AS total, COUNT(*) AS visits, "
        "MAX(created_at) AS last_seen FROM learning_history WHERE user_id = ? GROUP BY menu_id",
        (user_id,),
    )
    stats = {
        r[0]: {"total": float(r[1] or 0.0), "visits": int(r[2] or 0), "last_seen": r[3] or ""}
        for r in c.fetchall()
    }
    conn.close()
    return stats


def total_seconds(user_id: str) -> float:
    """사용자의 전체 누적 체류 시간(초)."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(waiting_time), 0) FROM learning_history WHERE user_id = ?", (user_id,))
    total = float(c.fetchone()[0] or 0.0)
    conn.close()
    return total
