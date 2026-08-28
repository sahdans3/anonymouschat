import os
import psycopg2
import psycopg2.pool
import threading
import time
import logging
from datetime import datetime, timedelta
import random
import string

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    logger.error("❌ DATABASE_URL tidak ditemukan! Pastikan sudah di set di Railway Variables")
else:
    logger.info(f"✅ DATABASE_URL ditemukan")

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
    if not DATABASE_URL:
        logger.error("❌ DATABASE_URL is empty or not set!")
        return None
    
    try:
        pool = get_db_pool()
        if pool:
            try:
                conn = pool.getconn()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    return conn
            except psycopg2.pool.PoolError:
                logger.warning("⚠️ Pool exhausted, creating direct connection")
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
                return conn
        else:
            logger.info("📌 Creating direct connection to database...")
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
            return conn
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        return None

def return_connection(conn):
    if conn:
        try:
            pool = get_db_pool()
            if pool:
                try:
                    pool.putconn(conn)
                except Exception as e:
                    logger.warning(f"⚠️ Error putting connection back to pool: {e}")
                    try:
                        conn.close()
                    except:
                        pass
            else:
                try:
                    conn.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"⚠️ Error returning connection: {e}")
            try:
                conn.close()
            except:
                pass

# ================= INIT DATABASE =================

def init_db():
    if not DATABASE_URL:
        logger.warning("⚠️ Skipping database init (no DATABASE_URL)")
        return
    
    db = connect_db()
    if not db:
        logger.error("❌ Cannot initialize database")
        return
    
    cursor = db.cursor()
    
    # ============ CREATE TABLES ============
    logger.info("📌 Creating tables...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            searching INT DEFAULT 0,
            partner_id BIGINT DEFAULT NULL,
            gender VARCHAR(10) DEFAULT NULL,
            preferred_gender VARCHAR(10) DEFAULT NULL,
            premium INT DEFAULT 0,
            premium_expiry TIMESTAMP DEFAULT NULL,
            partner_count INT DEFAULT 0,
            last_partner_reset TIMESTAMP DEFAULT NULL,
            referral_code VARCHAR(20) UNIQUE DEFAULT NULL,
            referred_by BIGINT DEFAULT NULL,
            referral_count INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            from_user BIGINT NOT NULL,
            to_user BIGINT NOT NULL,
            feedback VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waiting_queue (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            gender VARCHAR(10) DEFAULT NULL,
            preferred_gender VARCHAR(10) DEFAULT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            user1 BIGINT NOT NULL,
            user2 BIGINT NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP DEFAULT NULL,
            message_count INT DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waiting_messages (
            user_id BIGINT PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            message_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            item_name VARCHAR(255) NOT NULL,
            item_price INT NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            payment_method VARCHAR(50) DEFAULT 'stars',
            payment_id VARCHAR(100) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP DEFAULT NULL,
            completed_at TIMESTAMP DEFAULT NULL,
            metadata JSONB DEFAULT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase_log (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            action VARCHAR(50) NOT NULL,
            purchase_id INT REFERENCES purchase(id) ON DELETE SET NULL,
            details JSONB DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ============ ADD MISSING COLUMNS ============
    logger.info("📌 Adding missing columns...")
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS filter_gender VARCHAR(10) DEFAULT NULL")
        logger.info("   ✅ filter_gender added")
    except Exception as e:
        logger.warning(f"   ⚠️ filter_gender: {e}")
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active TIMESTAMP DEFAULT NULL")
        logger.info("   ✅ last_active added")
    except Exception as e:
        logger.warning(f"   ⚠️ last_active: {e}")
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_matches INT DEFAULT 0")
        logger.info("   ✅ total_matches added")
    except Exception as e:
        logger.warning(f"   ⚠️ total_matches: {e}")
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE")
        logger.info("   ✅ is_banned added")
    except Exception as e:
        logger.warning(f"   ⚠️ is_banned: {e}")
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason TEXT DEFAULT NULL")
        logger.info("   ✅ ban_reason added")
    except Exception as e:
        logger.warning(f"   ⚠️ ban_reason: {e}")
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS language_code VARCHAR(10) DEFAULT 'en'")
        logger.info("   ✅ language_code added")
    except Exception as e:
        logger.warning(f"   ⚠️ language_code: {e}")
    
    try:
        cursor.execute("ALTER TABLE waiting_queue ADD COLUMN IF NOT EXISTS filter_gender VARCHAR(10) DEFAULT NULL")
        logger.info("   ✅ waiting_queue.filter_gender added")
    except Exception as e:
        logger.warning(f"   ⚠️ waiting_queue.filter_gender: {e}")
    
    try:
        cursor.execute("ALTER TABLE waiting_queue ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE")
        logger.info("   ✅ waiting_queue.is_premium added")
    except Exception as e:
        logger.warning(f"   ⚠️ waiting_queue.is_premium: {e}")
    
    try:
        cursor.execute("ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS messages_count INT DEFAULT 0")
        logger.info("   ✅ chat_history.messages_count added")
    except Exception as e:
        logger.warning(f"   ⚠️ chat_history.messages_count: {e}")
    
    try:
        cursor.execute("ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMP DEFAULT NULL")
        logger.info("   ✅ chat_history.last_message_at added")
    except Exception as e:
        logger.warning(f"   ⚠️ chat_history.last_message_at: {e}")
    
    # ============ CREATE INDEXES ============
    logger.info("📌 Creating indexes...")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_filter_gender ON users(filter_gender)")
        logger.info("   ✅ idx_users_filter_gender")
    except Exception as e:
        logger.warning(f"   ⚠️ idx_users_filter_gender: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active)")
        logger.info("   ✅ idx_users_last_active")
    except Exception as e:
        logger.warning(f"   ⚠️ idx_users_last_active: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_banned ON users(is_banned)")
        logger.info("   ✅ idx_users_is_banned")
    except Exception as e:
        logger.warning(f"   ⚠️ idx_users_is_banned: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_user_id ON purchase(user_id)")
        logger.info("   ✅ idx_purchase_user_id")
    except Exception as e:
        logger.warning(f"   ⚠️ idx_purchase_user_id: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_status ON purchase(status)")
        logger.info("   ✅ idx_purchase_status")
    except Exception as e:
        logger.warning(f"   ⚠️ idx_purchase_status: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_log_user_id ON purchase_log(user_id)")
        logger.info("   ✅ idx_purchase_log_user_id")
    except Exception as e:
        logger.warning(f"   ⚠️ idx_purchase_log_user_id: {e}")
    
    # ============ AUTO-MATCH TRIGGER ===========
    
    db.commit()
    cursor.close()
    return_connection(db)
    logger.info("✅ Database initialization complete!")

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
        cursor.execute("INSERT INTO users(user_id) VALUES(%s) ON CONFLICT (user_id) DO NOTHING", (user_id,))
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
        cursor.execute("UPDATE users SET searching=0, partner_id=NULL WHERE user_id=%s", (user_id,))
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
        cursor.execute("UPDATE users SET searching=%s WHERE user_id=%s", (status, user_id))
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
        cursor.execute("SELECT gender, preferred_gender, premium FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        gender = result[0] if result else None
        preferred_gender = result[1] if result else None
        is_premium = True if result and result[2] == 1 else False
        
        cursor.execute("SELECT user_id FROM waiting_queue WHERE user_id=%s", (user_id,))
        if cursor.fetchone():
            return
        
        cursor.execute("SELECT partner_id FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        if result and result[0] is not None:
            return
        
        cursor.execute("""
            INSERT INTO waiting_queue(user_id, gender, preferred_gender, created_at, is_premium) 
            VALUES(%s, %s, %s, CURRENT_TIMESTAMP, %s)
            ON CONFLICT (user_id) DO NOTHING
        """, (user_id, gender, preferred_gender, is_premium))
        
        db.commit()
        logger.info(f"✅ User {user_id} joined queue (premium: {is_premium}, gender: {gender})")
        logger.info(f"🟡 QUEUE ADD: user={user_id}, gender={gender}, premium={is_premium}")
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
    if not DATABASE_URL:
        return None

    db = connect_db()
    if not db:
        return None

    cursor = None
    try:
        cursor = db.cursor()
        
        # Pastikan user belum punya partner
        cursor.execute("""
            SELECT partner_id
            FROM users
            WHERE user_id = %s
        """, (user_id,))

        row = cursor.fetchone()

        if not row:
            return None

        if row[0] is not None:
            logger.info(f"🔎 User {user_id} already has partner: {row[0]}")
            return None

        # Pastikan user sedang waiting
        cursor.execute("""
            SELECT user_id
            FROM waiting_queue
            WHERE user_id = %s
        """, (user_id,))

        if not cursor.fetchone():
            logger.info(f"🔎 User {user_id} not in waiting_queue")
            return None

        logger.info(f"🔎 FIND PARTNER: user={user_id}")

        # Cari user lain yang sedang waiting
        cursor.execute("""
            SELECT user_id
            FROM waiting_queue
            WHERE user_id <> %s
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """, (user_id,))

        row = cursor.fetchone()

        if not row:
            logger.info(f"🔎 No partner found for {user_id}")
            return None

        partner_id = row[0]
        logger.info(f"🔎 CANDIDATE: {partner_id}")

        # Pastikan partner belum punya pasangan
        cursor.execute("""
            SELECT partner_id
            FROM users
            WHERE user_id = %s
        """, (partner_id,))

        partner_row = cursor.fetchone()

        if not partner_row:
            return None

        if partner_row[0] is not None:
            logger.info(f"🔎 Partner {partner_id} already has partner: {partner_row[0]}")
            cursor.execute("""
                DELETE FROM waiting_queue
                WHERE user_id = %s
            """, (partner_id,))
            db.commit()
            return None

        # =========================
        # MATCH!
        # =========================

        cursor.execute("""
            UPDATE users
            SET partner_id = %s,
                searching = 0
            WHERE user_id = %s
        """, (partner_id, user_id))

        cursor.execute("""
            UPDATE users
            SET partner_id = %s,
                searching = 0
            WHERE user_id = %s
        """, (user_id, partner_id))

        cursor.execute("""
            DELETE FROM waiting_queue
            WHERE user_id IN (%s, %s)
        """, (user_id, partner_id))

        cursor.execute("""
            INSERT INTO chat_history(user1, user2, start_time)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
        """, (user_id, partner_id))

        db.commit()

        logger.info(f"⚡ MATCH FOUND: {user_id} <-> {partner_id}")
        return partner_id

    except Exception as e:
        logger.error(f"❌ find_partner error for {user_id}: {e}")
        try:
            db.rollback()
        except:
            pass
        return None

    finally:
        # 🔥 PASTIKAN CURSOR DAN KONEKSI DITUTUP!
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if db:
            try:
                return_connection(db)
            except Exception as e:
                logger.warning(f"⚠️ Error returning connection: {e}")

def stop_chat(user_id):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("SELECT partner_id FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        partner_id = result[0] if result else None
        
        cursor.execute("UPDATE users SET partner_id=NULL, searching=0 WHERE user_id=%s", (user_id,))
        if partner_id:
            cursor.execute("UPDATE users SET partner_id=NULL, searching=0 WHERE user_id=%s", (partner_id,))
        
        leave_queue(user_id)
        if partner_id:
            leave_queue(partner_id)
        
        db.commit()
        logger.info(f"✅ Chat stopped: {user_id} with {partner_id}")
        return partner_id
        
    except Exception as e:
        logger.error(f"❌ Stop chat error: {e}")
        db.rollback()
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

def get_user_gender(user_id):
    if not DATABASE_URL:
        return None, None
    db = connect_db()
    if not db:
        return None, None
    cursor = db.cursor()
    try:
        cursor.execute("SELECT gender, preferred_gender FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0], result[1]
        return None, None
    except Exception as e:
        logger.error(f"❌ Get user gender error: {e}")
        return None, None
    finally:
        cursor.close()
        return_connection(db)

def set_gender(user_id, gender):
    if not DATABASE_URL:
        return False
    db = connect_db()
    if not db:
        return False
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET gender=%s WHERE user_id=%s", (gender, user_id))
        db.commit()
        logger.info(f"✅ User {user_id} set gender to {gender}")
        return True
    except Exception as e:
        logger.error(f"❌ Set gender error: {e}")
        db.rollback()
        return False
    finally:
        cursor.close()
        return_connection(db)

def set_preferred_gender(user_id, gender):
    if not DATABASE_URL:
        return False
    db = connect_db()
    if not db:
        return False
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET preferred_gender=%s WHERE user_id=%s", (gender, user_id))
        db.commit()
        logger.info(f"✅ User {user_id} set preferred gender to {gender}")
        return True
    except Exception as e:
        logger.error(f"❌ Set preferred gender error: {e}")
        db.rollback()
        return False
    finally:
        cursor.close()
        return_connection(db)

# ================= PREMIUM FUNCTIONS =================

def check_premium(user_id):
    if not DATABASE_URL:
        return False
    db = connect_db()
    if not db:
        return False
    cursor = db.cursor()
    try:
        cursor.execute("SELECT premium, premium_expiry FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        if not result:
            return False
        premium, expiry = result
        if premium == 1:
            if expiry:
                cursor.execute("SELECT CURRENT_TIMESTAMP <= %s", (expiry,))
                is_valid = cursor.fetchone()[0]
                if not is_valid:
                    cursor.execute("UPDATE users SET premium=0 WHERE user_id=%s", (user_id,))
                    db.commit()
                    return False
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Check premium error: {e}")
        return False
    finally:
        cursor.close()
        return_connection(db)

def set_premium(user_id, days=30):
    if not DATABASE_URL:
        return False
    db = connect_db()
    if not db:
        return False
    cursor = db.cursor()
    try:
        cursor.execute("SELECT premium_expiry FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        current_expiry = result[0] if result else None
        
        if current_expiry:
            cursor.execute("SELECT CURRENT_TIMESTAMP <= %s", (current_expiry,))
            is_valid = cursor.fetchone()[0]
            if is_valid:
                cursor.execute("""
                    UPDATE users 
                    SET premium = 1, 
                        premium_expiry = premium_expiry + INTERVAL '%s days',
                        partner_count = 0,
                        last_partner_reset = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (days, user_id))
                logger.info(f"✅ User {user_id} extended premium by {days} days")
            else:
                cursor.execute("""
                    UPDATE users 
                    SET premium = 1, 
                        premium_expiry = CURRENT_TIMESTAMP + INTERVAL '%s days',
                        partner_count = 0,
                        last_partner_reset = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (days, user_id))
                logger.info(f"✅ User {user_id} renewed premium for {days} days")
        else:
            cursor.execute("""
                UPDATE users 
                SET premium = 1, 
                    premium_expiry = CURRENT_TIMESTAMP + INTERVAL '%s days',
                    partner_count = 0,
                    last_partner_reset = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """, (days, user_id))
            logger.info(f"✅ User {user_id} set as premium for {days} days")
        
        db.commit()
        
        cursor.execute("SELECT premium FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 1
        
    except Exception as e:
        logger.error(f"❌ Set premium error: {e}")
        db.rollback()
        return False
    finally:
        cursor.close()
        return_connection(db)

def get_premium_status(user_id):
    if not DATABASE_URL:
        return False, None
    db = connect_db()
    if not db:
        return False, None
    cursor = db.cursor()
    try:
        cursor.execute("SELECT premium, premium_expiry FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0] == 1, result[1]
        return False, None
    except Exception as e:
        logger.error(f"❌ Get premium status error: {e}")
        return False, None
    finally:
        cursor.close()
        return_connection(db)

# ================= PARTNER COUNT =================

def increment_partner_count(user_id):
    if not DATABASE_URL:
        return
    db = connect_db()
    if not db:
        return
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET partner_count = partner_count + 1 WHERE user_id = %s", (user_id,))
        db.commit()
    except Exception as e:
        logger.error(f"❌ Increment partner count error: {e}")
        db.rollback()
    finally:
        cursor.close()
        return_connection(db)

def get_partner_count(user_id):
    if not DATABASE_URL:
        return 0
    db = connect_db()
    if not db:
        return 0
    cursor = db.cursor()
    try:
        cursor.execute("SELECT partner_count FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"❌ Get partner count error: {e}")
        return 0
    finally:
        cursor.close()
        return_connection(db)

def reset_partner_count(user_id):
    if not DATABASE_URL:
        return
    db = connect_db()
    if not db:
        return
    cursor = db.cursor()
    try:
        cursor.execute("""
            UPDATE users 
            SET partner_count = 0, last_partner_reset = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (user_id,))
        db.commit()
    except Exception as e:
        logger.error(f"❌ Reset partner count error: {e}")
        db.rollback()
    finally:
        cursor.close()
        return_connection(db)

def get_last_partner_reset(user_id):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("SELECT last_partner_reset FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"❌ Get last reset error: {e}")
        return None
    finally:
        cursor.close()
        return_connection(db)

def check_daily_limit(user_id, limit=6, cooldown_hours=19):
    if not DATABASE_URL:
        return True, 0, None
    
    db = connect_db()
    if not db:
        return True, 0, None
    
    cursor = db.cursor()
    try:
        cursor.execute("SELECT premium FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        is_premium = result and result[0] == 1
        
        if is_premium:
            return True, 0, None
        
        cursor.execute("SELECT partner_count, last_partner_reset FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        if not result:
            return True, 0, None
        
        partner_count = result[0] or 0
        last_reset = result[1]
        
        if not last_reset:
            reset_partner_count(user_id)
            return True, 0, None
        
        elapsed = (datetime.now() - last_reset).total_seconds() / 3600
        if elapsed >= cooldown_hours:
            reset_partner_count(user_id)
            return True, 0, None
        
        if partner_count >= limit:
            remaining_hours = int(cooldown_hours - elapsed)
            return False, partner_count, remaining_hours
        
        return True, partner_count, None
        
    except Exception as e:
        logger.error(f"❌ Check daily limit error: {e}")
        return True, 0, None
    finally:
        cursor.close()
        return_connection(db)

# ================= CHAT HISTORY =================

def start_chat_session(user1, user2):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO chat_history(user1, user2, start_time)
            VALUES(%s, %s, CURRENT_TIMESTAMP)
            RETURNING id
        """, (user1, user2))
        chat_id = cursor.fetchone()[0]
        db.commit()
        return chat_id
    except Exception as e:
        logger.error(f"❌ Start chat session error: {e}")
        db.rollback()
        return None
    finally:
        cursor.close()
        return_connection(db)

def end_chat_session(user_id):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("""
            SELECT id, user1, user2
            FROM chat_history
            WHERE (user1 = %s OR user2 = %s) AND end_time IS NULL
            ORDER BY start_time DESC
            LIMIT 1
        """, (user_id, user_id))
        result = cursor.fetchone()
        if not result:
            return None
        chat_id, user1, user2 = result
        cursor.execute("UPDATE chat_history SET end_time = CURRENT_TIMESTAMP WHERE id = %s", (chat_id,))
        db.commit()
        return chat_id
    except Exception as e:
        logger.error(f"❌ End chat session error: {e}")
        db.rollback()
        return None
    finally:
        cursor.close()
        return_connection(db)

def get_chat_report(chat_id):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("""
            SELECT id, user1, user2, start_time, end_time,
                   EXTRACT(EPOCH FROM (end_time - start_time)) as duration_seconds
            FROM chat_history WHERE id = %s
        """, (chat_id,))
        result = cursor.fetchone()
        if not result:
            return None
        return {
            'id': result[0],
            'user1': result[1],
            'user2': result[2],
            'start_time': result[3],
            'end_time': result[4],
            'duration': int(result[5] or 0)
        }
    except Exception as e:
        logger.error(f"❌ Get chat report error: {e}")
        return None
    finally:
        cursor.close()
        return_connection(db)

# ================= WAITING MESSAGES =================

def save_waiting_message(user_id, chat_id, message_id):
    if not DATABASE_URL:
        return
    db = connect_db()
    if not db:
        return
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO waiting_messages (user_id, chat_id, message_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET chat_id = EXCLUDED.chat_id, message_id = EXCLUDED.message_id
        """, (user_id, chat_id, message_id))
        db.commit()
    except Exception as e:
        logger.error(f"❌ Save waiting message error: {e}")
        db.rollback()
    finally:
        cursor.close()
        return_connection(db)

def delete_waiting_message(user_id):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM waiting_messages WHERE user_id = %s RETURNING chat_id, message_id", (user_id,))
        result = cursor.fetchone()
        db.commit()
        return result
    except Exception as e:
        logger.error(f"❌ Delete waiting message error: {e}")
        db.rollback()
        return None
    finally:
        cursor.close()
        return_connection(db)

# ================= REFERRAL =================

def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def create_referral_code(user_id):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("SELECT referral_code FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        if result and result[0]:
            return result[0]
        
        code = generate_referral_code()
        while True:
            cursor.execute("SELECT user_id FROM users WHERE referral_code=%s", (code,))
            if not cursor.fetchone():
                break
            code = generate_referral_code()
        
        cursor.execute("UPDATE users SET referral_code=%s WHERE user_id=%s", (code, user_id))
        db.commit()
        return code
    except Exception as e:
        logger.error(f"❌ Create referral code error: {e}")
        db.rollback()
        return None
    finally:
        cursor.close()
        return_connection(db)

def get_referral_code(user_id):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("SELECT referral_code FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"❌ Get referral code error: {e}")
        return None
    finally:
        cursor.close()
        return_connection(db)

def use_referral_code(new_user_id, code):
    if not DATABASE_URL:
        return False, "System error"
    db = connect_db()
    if not db:
        return False, "Database error"
    cursor = db.cursor()
    try:
        cursor.execute("SELECT user_id, referral_count FROM users WHERE referral_code=%s", (code,))
        result = cursor.fetchone()
        if not result:
            return False, "Invalid referral code"
        
        referrer_id = result[0]
        if referrer_id == new_user_id:
            return False, "You cannot use your own referral code"
        
        cursor.execute("SELECT referred_by FROM users WHERE user_id=%s", (new_user_id,))
        result = cursor.fetchone()
        if result and result[0]:
            return False, "You have already used a referral code"
        
        cursor.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = %s", (referrer_id,))
        cursor.execute("UPDATE users SET referred_by = %s WHERE user_id = %s", (referrer_id, new_user_id))
        db.commit()
        return True, referrer_id
    except Exception as e:
        logger.error(f"❌ Use referral code error: {e}")
        db.rollback()
        return False, str(e)
    finally:
        cursor.close()
        return_connection(db)

def get_referral_stats(user_id):
    if not DATABASE_URL:
        return 0, []
    db = connect_db()
    if not db:
        return 0, []
    cursor = db.cursor()
    try:
        cursor.execute("SELECT referral_count FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        count = result[0] if result else 0
        
        cursor.execute("""
            SELECT user_id, created_at FROM users 
            WHERE referred_by = %s ORDER BY created_at DESC LIMIT 10
        """, (user_id,))
        referred = cursor.fetchall()
        return count, referred
    except Exception as e:
        logger.error(f"❌ Get referral stats error: {e}")
        return 0, []
    finally:
        cursor.close()
        return_connection(db)

def is_referred(user_id):
    if not DATABASE_URL:
        return False
    db = connect_db()
    if not db:
        return False
    cursor = db.cursor()
    try:
        cursor.execute("SELECT referred_by FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        return result and result[0] is not None
    except Exception as e:
        logger.error(f"❌ Is referred error: {e}")
        return False
    finally:
        cursor.close()
        return_connection(db)

def get_referrer(user_id):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("SELECT referred_by FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"❌ Get referrer error: {e}")
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