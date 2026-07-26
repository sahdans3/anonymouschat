import os
import psycopg2
import psycopg2.pool
import threading
import time
import logging
import random

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= CEK DATABASE_URL =================

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    logger.error("❌ DATABASE_URL tidak ditemukan!")
    logger.info("📋 Pastikan sudah menambahkan PostgreSQL di Railway:")
    logger.info("   railway add → Database → PostgreSQL")
else:
    logger.info("✅ DATABASE_URL ditemukan")

# ================= CONNECTION POOL =================

db_pool = None

def get_db_pool():
    global db_pool
    if db_pool is None and DATABASE_URL:
        try:
            db_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=DATABASE_URL
            )
            logger.info("✅ Database connection pool created")
        except Exception as e:
            logger.error(f"❌ Failed to create pool: {e}")
            db_pool = None
    return db_pool

def connect_db():
    """Get connection from pool"""
    if not DATABASE_URL:
        return None
    try:
        pool = get_db_pool()
        if pool:
            try:
                # Hapus parameter timeout
                return pool.getconn()
            except psycopg2.pool.PoolError:
                logger.warning("⚠️ Pool exhausted, creating direct connection")
                return psycopg2.connect(DATABASE_URL)
        else:
            return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"⚠️ Database connection error: {e}")
        return None

def return_connection(conn):
    """Return connection to pool or close if pool not available"""
    if conn:
        try:
            pool = get_db_pool()
            if pool:
                pool.putconn(conn)
            else:
                conn.close()
        except Exception as e:
            logger.error(f"⚠️ Error returning connection: {e}")
            try:
                conn.close()
            except:
                pass

# ================= CREATE TABLES =================

def init_db():
    if not DATABASE_URL:
        logger.warning("⚠️ Skipping database init (no DATABASE_URL)")
        return
    
    db = connect_db()
    if not db:
        logger.error("❌ Cannot initialize database")
        return
    
    cursor = db.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            searching INT DEFAULT 0,
            partner_id BIGINT DEFAULT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Feedback table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            from_user BIGINT NOT NULL,
            to_user BIGINT NOT NULL,
            feedback VARCHAR(50) NOT NULL
        )
    """)
    
    # Waiting queue table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waiting_queue (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    db.commit()
    cursor.close()
    return_connection(db)
    logger.info("✅ Database tables created")

# ================= KEEP ALIVE =================

def keep_alive():
    while True:
        try:
            if DATABASE_URL:
                db = connect_db()
                if db:
                    cursor = db.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchall()
                    cursor.close()
                    return_connection(db)
                    logger.info("✅ Database ping successful")
        except Exception as e:
            logger.error(f"❌ Database ping failed: {e}")
        time.sleep(300)

def start_keep_alive():
    if not DATABASE_URL:
        logger.warning("⚠️ Database keep-alive disabled (no DATABASE_URL)")
        return
    try:
        thread = threading.Thread(target=keep_alive, daemon=True)
        thread.start()
        logger.info("🔄 Database keep-alive started")
    except Exception as e:
        logger.error(f"⚠️ Failed to start keep-alive: {e}")

# ================= USER FUNCTIONS =================

def register_user(user_id):
    if not DATABASE_URL:
        return
    db = connect_db()
    if not db:
        return
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO users(user_id) 
            VALUES(%s) 
            ON CONFLICT (user_id) 
            DO UPDATE SET updated_at = CURRENT_TIMESTAMP
        """, (user_id,))
        db.commit()
    except Exception as e:
        logger.error(f"❌ Register user error: {e}")
        db.rollback()
    finally:
        cursor.close()
        return_connection(db)

def clear_user_status(user_id):
    if not DATABASE_URL:
        return
    db = connect_db()
    if not db:
        return
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET searching=0, partner_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE user_id=%s", (user_id,))
        cursor.execute("DELETE FROM waiting_queue WHERE user_id=%s", (user_id,))
        db.commit()
        logger.info(f"✅ Status user {user_id} cleared")
    except Exception as e:
        logger.error(f"❌ Clear status error: {e}")
        db.rollback()
    finally:
        cursor.close()
        return_connection(db)

def set_searching(user_id, status):
    if not DATABASE_URL:
        return
    db = connect_db()
    if not db:
        return
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET searching=%s, updated_at=CURRENT_TIMESTAMP WHERE user_id=%s", (status, user_id))
        db.commit()
    except Exception as e:
        logger.error(f"❌ Set searching error: {e}")
        db.rollback()
    finally:
        cursor.close()
        return_connection(db)

def is_searching(user_id):
    if not DATABASE_URL:
        return False
    db = connect_db()
    if not db:
        return False
    cursor = db.cursor()
    try:
        cursor.execute("SELECT searching FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 1
    except Exception as e:
        logger.error(f"❌ Is searching error: {e}")
        return False
    finally:
        cursor.close()
        return_connection(db)

def join_queue(user_id):
    if not DATABASE_URL:
        return
    db = connect_db()
    if not db:
        return
    cursor = db.cursor()
    try:
        # Cek apakah user sudah di queue
        cursor.execute("SELECT user_id FROM waiting_queue WHERE user_id=%s", (user_id,))
        if cursor.fetchone():
            return
        
        # Cek apakah user sedang dalam chat
        cursor.execute("SELECT partner_id FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        if result and result[0] is not None:
            return
        
        cursor.execute("INSERT INTO waiting_queue(user_id) VALUES(%s) ON CONFLICT (user_id) DO NOTHING", (user_id,))
        db.commit()
        logger.info(f"✅ User {user_id} joined queue")
    except Exception as e:
        logger.error(f"❌ Join queue error: {e}")
        db.rollback()
    finally:
        cursor.close()
        return_connection(db)

def leave_queue(user_id):
    if not DATABASE_URL:
        return
    db = connect_db()
    if not db:
        return
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM waiting_queue WHERE user_id=%s", (user_id,))
        db.commit()
    except Exception as e:
        logger.error(f"❌ Leave queue error: {e}")
        db.rollback()
    finally:
        cursor.close()
        return_connection(db)

def find_partner(user_id):
    """Find partner with robust locking and retry mechanism"""
    if not DATABASE_URL:
        logger.warning(f"⚠️ No DATABASE_URL for user {user_id}")
        return None
    
    db = connect_db()
    if not db:
        logger.error(f"❌ Cannot connect to database for user {user_id}")
        return None
    
    cursor = db.cursor()
    
    try:
        cursor.execute("BEGIN")
        
        # Cek apakah user sedang dalam chat
        cursor.execute("SELECT partner_id, searching FROM users WHERE user_id=%s FOR UPDATE", (user_id,))
        user_check = cursor.fetchone()
        
        if user_check and user_check[0] is not None:
            logger.info(f"ℹ️ User {user_id} already in chat")
            cursor.execute("COMMIT")
            return None
        
        # Cari partner di queue
        cursor.execute("""
            SELECT wq.user_id, u.searching
            FROM waiting_queue wq
            JOIN users u ON u.user_id = wq.user_id
            WHERE wq.user_id <> %s
                AND (u.partner_id IS NULL OR u.partner_id = 0)
                AND u.searching = 1
            ORDER BY wq.created_at ASC, random()
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """, (user_id,))
        
        partner = cursor.fetchone()
        
        if not partner:
            logger.info(f"ℹ️ No partner in queue for user {user_id}")
            cursor.execute("COMMIT")
            return None
        
        partner_id = partner[0]
        logger.info(f"🔍 Found potential partner: {partner_id}")
        
        # Lock partner row
        cursor.execute("SELECT partner_id, searching FROM users WHERE user_id=%s FOR UPDATE", (partner_id,))
        partner_check = cursor.fetchone()
        
        if partner_check and partner_check[0] is not None:
            logger.info(f"ℹ️ Partner {partner_id} already in chat, cleaning up...")
            leave_queue(partner_id)
            cursor.execute("COMMIT")
            return None
        
        # Update kedua user
        cursor.execute("UPDATE users SET partner_id=%s, searching=0, updated_at=CURRENT_TIMESTAMP WHERE user_id=%s", (partner_id, user_id))
        cursor.execute("UPDATE users SET partner_id=%s, searching=0, updated_at=CURRENT_TIMESTAMP WHERE user_id=%s", (user_id, partner_id))
        
        # Hapus dari queue
        cursor.execute("DELETE FROM waiting_queue WHERE user_id IN (%s, %s)", (user_id, partner_id))
        
        cursor.execute("COMMIT")
        logger.info(f"✅ Partner found: {user_id} <-> {partner_id}")
        return partner_id
        
    except Exception as e:
        logger.error(f"❌ Find partner error for user {user_id}: {e}")
        try:
            cursor.execute("ROLLBACK")
        except:
            pass
        return None
    finally:
        cursor.close()
        return_connection(db)

def stop_chat(user_id):
    """Stop chat with locking to prevent race conditions"""
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("BEGIN")
        
        # Lock user row
        cursor.execute("SELECT partner_id FROM users WHERE user_id=%s FOR UPDATE", (user_id,))
        result = cursor.fetchone()
        partner_id = result[0] if result else None
        
        # Update user
        cursor.execute("UPDATE users SET partner_id=NULL, searching=0, updated_at=CURRENT_TIMESTAMP WHERE user_id=%s", (user_id,))
        
        # Update partner jika ada
        if partner_id:
            cursor.execute("SELECT partner_id FROM users WHERE user_id=%s FOR UPDATE", (partner_id,))
            cursor.execute("UPDATE users SET partner_id=NULL, searching=0, updated_at=CURRENT_TIMESTAMP WHERE user_id=%s", (partner_id,))
        
        # Hapus dari queue
        leave_queue(user_id)
        if partner_id:
            leave_queue(partner_id)
        
        cursor.execute("COMMIT")
        logger.info(f"✅ Chat stopped: {user_id} with {partner_id}")
        return partner_id
        
    except Exception as e:
        logger.error(f"❌ Stop chat error: {e}")
        try:
            cursor.execute("ROLLBACK")
        except:
            pass
        return None
    finally:
        cursor.close()
        return_connection(db)

def get_partner(user_id):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("SELECT partner_id FROM users WHERE user_id=%s AND partner_id IS NOT NULL", (user_id,))
        result = cursor.fetchone()
        if result and result[0]:
            partner_id = result[0]
            cursor.execute("SELECT user_id FROM users WHERE user_id=%s AND partner_id=%s", (partner_id, user_id))
            if cursor.fetchone():
                return partner_id
            else:
                cursor.execute("UPDATE users SET partner_id=NULL, searching=0 WHERE user_id=%s", (user_id,))
                db.commit()
                return None
        return None
    except Exception as e:
        logger.error(f"❌ Get partner error: {e}")
        return None
    finally:
        cursor.close()
        return_connection(db)

def remove_user(user_id):
    if not DATABASE_URL:
        return
    db = connect_db()
    if not db:
        return
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
        cursor.execute("DELETE FROM waiting_queue WHERE user_id=%s", (user_id,))
        db.commit()
        logger.info(f"✅ User {user_id} removed from database")
    except Exception as e:
        logger.error(f"❌ Remove user error: {e}")
        db.rollback()
    finally:
        cursor.close()
        return_connection(db)

def get_user_status(user_id):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        return result
    except Exception as e:
        logger.error(f"❌ Get user status error: {e}")
        return None
    finally:
        cursor.close()
        return_connection(db)

def save_feedback(from_user, to_user, feedback):
    if not DATABASE_URL:
        return
    db = connect_db()
    if not db:
        return
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO feedback(from_user, to_user, feedback) VALUES(%s, %s, %s)", (from_user, to_user, feedback))
        db.commit()
    except Exception as e:
        logger.error(f"❌ Save feedback error: {e}")
        db.rollback()
    finally:
        cursor.close()
        return_connection(db)