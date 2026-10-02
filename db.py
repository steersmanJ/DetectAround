import sqlite3
import os
from datetime import datetime

DB_PATH = "agri_detect.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # 탐지 이력 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            lat REAL,
            lon REAL,
            pnu TEXT,
            jibun TEXT,
            jimok TEXT,
            ndvi REAL,
            poly_coords TEXT
        )
    ''')
    # 보고서 생성 이력 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detection_id INTEGER,
            pnu TEXT,
            report_time TEXT,
            has_warnings BOOLEAN,
            FOREIGN KEY(detection_id) REFERENCES detections(id)
        )
    ''')
    conn.commit()
    conn.close()

def save_detection(lat, lon, pnu, jibun, jimok, ndvi, poly_coords_str=""):
    conn = get_connection()
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute('''
        INSERT INTO detections (timestamp, lat, lon, pnu, jibun, jimok, ndvi, poly_coords)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, lat, lon, pnu, jibun, jimok, ndvi, poly_coords_str))
    record_id = c.lastrowid
    conn.commit()
    conn.close()
    return record_id

def save_report(detection_id, pnu, has_warnings=False):
    conn = get_connection()
    c = conn.cursor()
    report_time = datetime.now().isoformat()
    c.execute('''
        INSERT INTO reports (detection_id, pnu, report_time, has_warnings)
        VALUES (?, ?, ?, ?)
    ''', (detection_id, pnu, report_time, has_warnings))
    conn.commit()
    conn.close()

def get_history():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT d.id, d.timestamp, d.pnu, d.jibun, d.jimok, d.ndvi, r.report_time
        FROM detections d
        LEFT JOIN reports r ON d.id = r.detection_id
        ORDER BY d.timestamp DESC
        LIMIT 100
    ''')
    rows = c.fetchall()
    conn.close()
    return rows

# DB 초기화
init_db()
