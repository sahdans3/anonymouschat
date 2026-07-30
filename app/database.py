import os
import psycopg2
import psycopg2.pool
import threading
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= CEK DATABASE_URL =================

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    logger.error("❌ DATABASE_URL tidak ditemukan!")
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
    if not DATABASE_URL:
        return None
    try:
        pool = get_db_pool()
        if pool:
            try:
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
    
    # Users table with gender and premium columns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            searching INT DEFAULT 0,
            partner_id BIGINT DEFAULT NULL,
            gender VARCHAR(10) DEFAULT NULL,
            preferred_gender VARCHAR(10) DEFAULT NULL,
            premium INT DEFAULT 0,
            premium_expiry TIMESTAMP DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    
    # Waiting queue table with gender info
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waiting_queue (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            gender VARCHAR(10) DEFAULT NULL,
            preferred_gender VARCHAR(10) DEFAULT NULL
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

# ================= PREMIUM FUNCTIONS =================

def check_premium(user_id):
    """Check if user has premium access"""
    if not DATABASE_URL:
        return False
    db = connect_db()
    if not db:
        return False
    cursor = db.cursor()
    try:
        cursor.execute("""
            SELECT premium, premium_expiry 
            FROM users 
            WHERE user_id=%s
        """, (user_id,))
        result = cursor.fetchone()
        if not result:
            return False
        premium, expiry = result
        # premium adalah integer (1 atau 0)
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
    """Set user as premium for X days"""
    if not DATABASE_URL:
        return False
    db = connect_db()
    if not db:
        return False
    cursor = db.cursor()
    try:
        cursor.execute("""
            UPDATE users 
            SET premium=1, 
                premium_expiry=CURRENT_TIMESTAMP + INTERVAL '%s days'
            WHERE user_id=%s
        """, (days, user_id))
        db.commit()
        logger.info(f"✅ User {user_id} set as premium for {days} days")
        return True
    except Exception as e:
        logger.error(f"❌ Set premium error: {e}")
        db.rollback()
        return False
    finally:
        cursor.close()
        return_connection(db)

def set_gender(user_id, gender):
    """Set user's gender"""
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
    """Set user's preferred gender for partner"""
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

def get_user_gender(user_id):
    """Get user's gender and preferred gender"""
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

def get_premium_status(user_id):
    """Get user's premium status and expiry"""
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
            # premium adalah integer (1 atau 0)
            return result[0] == 1, result[1]
        return False, None
    except Exception as e:
        logger.error(f"❌ Get premium status error: {e}")
        return False, None
    finally:
        cursor.close()
        return_connection(db)

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
            DO NOTHING
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
    """Add user to queue with priority"""
    if not DATABASE_URL:
        return
    db = connect_db()
    if not db:
        return
    cursor = db.cursor()
    try:
        # Get user gender and preferences
        cursor.execute("SELECT gender, preferred_gender, premium FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        gender = result[0] if result else None
        preferred_gender = result[1] if result else None
        is_premium = 1 if result and result[2] == 1 else 0
        
        # Cek apakah user sudah di queue
        cursor.execute("SELECT user_id FROM waiting_queue WHERE user_id=%s", (user_id,))
        if cursor.fetchone():
            return
        
        # Cek apakah user sedang dalam chat
        cursor.execute("SELECT partner_id FROM users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        if result and result[0] is not None:
            return
        
        # User tanpa gender (None) tetap bisa masuk queue
        # Premium user bisa filter gender, free user tidak
        if is_premium == 1 and preferred_gender and preferred_gender != 'any':
            cursor.execute("""
                INSERT INTO waiting_queue(user_id, gender, preferred_gender, created_at) 
                VALUES(%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, gender, preferred_gender))
        else:
            # Free user atau preferensi 'any': tidak ada filter gender
            cursor.execute("""
                INSERT INTO waiting_queue(user_id, gender, preferred_gender, created_at) 
                VALUES(%s, %s, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, gender))
        
        db.commit()
        logger.info(f"✅ User {user_id} joined queue (premium: {is_premium}, gender: {gender}, preferred: {preferred_gender if is_premium else 'any'})")
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
    """Find partner with instant matching - NO DELAY"""
    if not DATABASE_URL:
        return None
    
    db = connect_db()
    if not db:
        return None
    
    cursor = db.cursor()
    
    try:
        cursor.execute("BEGIN")
        
        # Check if user is already in chat
        cursor.execute("SELECT partner_id, searching FROM users WHERE user_id=%s FOR UPDATE", (user_id,))
        user_check = cursor.fetchone()
        if user_check and user_check[0] is not None:
            logger.info(f"ℹ️ User {user_id} already in chat")
            cursor.execute("COMMIT")
            return None
        
        # Get user gender and premium status
        cursor.execute("SELECT gender, preferred_gender, premium FROM users WHERE user_id=%s", (user_id,))
        user_info = cursor.fetchone()
        user_gender = user_info[0] if user_info else None
        user_preferred = user_info[1] if user_info else None
        is_premium = user_info[2] == 1 if user_info else False
        
        # FIRST: Try to find instant match (user searching but not in queue)
        # TIDAK perlu gender untuk instant match
        cursor.execute("""
            SELECT user_id 
            FROM users 
            WHERE user_id <> %s 
                AND searching = 1 
                AND partner_id IS NULL
                AND user_id NOT IN (SELECT user_id FROM waiting_queue)
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """, (user_id,))
        
        instant_partner = cursor.fetchone()
        
        if instant_partner:
            partner_id = instant_partner[0]
            logger.info(f"⚡ INSTANT MATCH: {user_id} <-> {partner_id}")
            
            cursor.execute("UPDATE users SET partner_id=%s, searching=0 WHERE user_id=%s", (partner_id, user_id))
            cursor.execute("UPDATE users SET partner_id=%s, searching=0 WHERE user_id=%s", (user_id, partner_id))
            cursor.execute("COMMIT")
            return partner_id
        
        # SECOND: Find partner from queue
        # Jika user premium dan punya preferred_gender dan preferred_gender != 'any' dan user punya gender
        if is_premium and user_preferred and user_preferred != 'any' and user_gender:
            query = """
                SELECT wq.user_id
                FROM waiting_queue wq
                JOIN users u ON u.user_id = wq.user_id
                WHERE wq.user_id <> %s
                    AND (u.partner_id IS NULL OR u.partner_id = 0)
                    AND u.searching = 1
                    AND u.gender = %s
                    AND wq.user_id NOT IN (
                        SELECT partner_id FROM users WHERE partner_id IS NOT NULL
                    )
                ORDER BY wq.created_at ASC, wq.id ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """
            params = (user_id, user_preferred)
        else:
            # Free user, atau user tanpa gender, atau preferensi 'any'
            # Cari siapa saja (tanpa filter gender)
            query = """
                SELECT wq.user_id
                FROM waiting_queue wq
                JOIN users u ON u.user_id = wq.user_id
                WHERE wq.user_id <> %s
                    AND (u.partner_id IS NULL OR u.partner_id = 0)
                    AND u.searching = 1
                    AND wq.user_id NOT IN (
                        SELECT partner_id FROM users WHERE partner_id IS NOT NULL
                    )
                ORDER BY wq.created_at ASC, wq.id ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """
            params = (user_id,)
        
        cursor.execute(query, params)
        partner = cursor.fetchone()
        
        if not partner:
            logger.info(f"ℹ️ No partner in queue for user {user_id}")
            cursor.execute("COMMIT")
            return None
        
        partner_id = partner[0]
        logger.info(f"🔍 Found partner in queue: {partner_id}")
        
        # Lock partner row
        cursor.execute("SELECT partner_id, searching FROM users WHERE user_id=%s FOR UPDATE", (partner_id,))
        partner_check = cursor.fetchone()
        if partner_check and partner_check[0] is not None:
            logger.info(f"ℹ️ Partner {partner_id} already in chat, cleaning up...")
            leave_queue(partner_id)
            cursor.execute("COMMIT")
            return None
        
        # Update both users
        cursor.execute("UPDATE users SET partner_id=%s, searching=0 WHERE user_id=%s", (partner_id, user_id))
        cursor.execute("UPDATE users SET partner_id=%s, searching=0 WHERE user_id=%s", (user_id, partner_id))
        cursor.execute("DELETE FROM waiting_queue WHERE user_id IN (%s, %s)", (user_id, partner_id))
        
        cursor.execute("COMMIT")
        logger.info(f"✅ Partner found from queue: {user_id} <-> {partner_id}")
        return partner_id
        
    except Exception as e:
        logger.error(f"❌ Find partner error: {e}")
        try:
            cursor.execute("ROLLBACK")
        except:
            pass
        return None
    finally:
        cursor.close()
        return_connection(db)

def stop_chat(user_id):
    if not DATABASE_URL:
        return None
    db = connect_db()
    if not db:
        return None
    cursor = db.cursor()
    try:
        cursor.execute("BEGIN")
        cursor.execute("SELECT partner_id FROM users WHERE user_id=%s FOR UPDATE", (user_id,))
        result = cursor.fetchone()
        partner_id = result[0] if result else None
        
        cursor.execute("UPDATE users SET partner_id=NULL, searching=0 WHERE user_id=%s", (user_id,))
        if partner_id:
            cursor.execute("SELECT partner_id FROM users WHERE user_id=%s FOR UPDATE", (partner_id,))
            cursor.execute("UPDATE users SET partner_id=NULL, searching=0 WHERE user_id=%s", (partner_id,))
        
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