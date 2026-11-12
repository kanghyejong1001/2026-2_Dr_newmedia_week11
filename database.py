import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "mycom.db"

def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    '''초기 테이블 생성 함수'''
    conn = get_db_connection()
    c = conn.cursor()
    # 사용자 테이블 생성
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_table (
        id_num INTEGER PRIMARY KEY AUTOINCREMENT,
        userid TEXT NOT NULL UNIQUE COLLATE NOCASE,
        username TEXT NOT NULL, 
        password TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    # 설문 테이블 생성
    c.execute('''
    CREATE TABLE IF NOT EXISTS survey_table (
        id_num INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        q1 INTEGER, q2 INTEGER, q3 INTEGER, q4 INTEGER, q5 INTEGER,
        q6 INTEGER, q7 INTEGER, q8 INTEGER, q9 INTEGER, q10 INTEGER,
        created_at TEXT
    )
    ''')
    # 학습 이력 테이블 생성 (11주차 기능)
    # - 메뉴를 클릭하는 순간 waiting_time=0 으로 INSERT (브라우저를 닫아도 행이 유실되지 않음)
    # - 다른 메뉴로 이동/로그아웃하는 순간 체류 시간(초)을 UPDATE
    c.execute('''
    CREATE TABLE IF NOT EXISTS learning_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        menu_id TEXT NOT NULL,
        waiting_time REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_history_user_menu ON learning_history (user_id, menu_id)')
    conn.commit()
    conn.close()

def create_user(userid, username, password, email):
    '''사용자 생성 함수. (성공 여부, 메시지) 튜플을 반환한다.'''
    userid = (userid or "").strip()
    username = (username or "").strip()
    password = password or ""
    email = (email or "").strip()

    # [수정] 빈 값으로 가입하면 빈 행이 그대로 저장되던 문제 수정
    if not userid:
        return False, "ID를 입력해 주세요."
    if not username:
        return False, "이름을 입력해 주세요."
    if not password:
        return False, "비밀번호를 입력해 주세요."
    if not email or "@" not in email:
        return False, "올바른 이메일 주소를 입력해 주세요."

    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        # [수정] 중복 원인(ID / 이메일)을 구분해서 안내
        c.execute("SELECT 1 FROM user_table WHERE userid = ?", (userid,))
        if c.fetchone():
            return False, "이미 존재하는 ID입니다."
        c.execute("SELECT 1 FROM user_table WHERE email = ?", (email,))
        if c.fetchone():
            return False, "이미 존재하는 이메일입니다."
        c.execute(
            "INSERT INTO user_table (userid, username, password, email) VALUES (?, ?, ?, ?)",
            (userid, username, password, email),
        )
        conn.commit()
        return True, "계정이 성공적으로 생성되었습니다."
    except sqlite3.Error as e:
        return False, f"DB 오류가 발생했습니다: {e}"
    finally:
        # [수정] 실패해도 연결이 반드시 닫히도록 finally 로 정리
        if conn is not None:
            conn.close()

def login_user(userid, password):
    '''사용자 로그인 함수'''
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM user_table WHERE userid=? AND password=?", (userid, password))
    data = c.fetchall()
    conn.close()
    return data

def insert_survey_data(user_id, q1, q2, q3, q4, q5, q6, q7, q8, q9, q10):
    '''설문 응답을 DB에 저장하는 함수'''
    conn = get_db_connection()
    c = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    query = """
    INSERT INTO survey_table (user_id, q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    c.execute(query, (user_id, q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, created_at))
    conn.commit()
    conn.close()

def fetch_survey_data():
    '''설문 결과를 Pandas DataFrame으로 불러오는 함수'''
    conn = get_db_connection()
    query = "SELECT * FROM survey_table"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
