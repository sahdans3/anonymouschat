def find_partner(user_id):
    """Find partner with instant matching - NO DELAY"""
    if not DATABASE_URL:
        return None
    
    db = connect_db()
    if not db:
        return None
    
    cursor = db.cursor()
    
    try:
        # Check if user is already in chat
        cursor.execute("SELECT partner_id, searching FROM users WHERE user_id=%s", (user_id,))
        user_check = cursor.fetchone()
        if user_check and user_check[0] is not None:
            logger.info(f"ℹ️ User {user_id} already in chat")
            return None
        
        # Get user gender and premium status
        cursor.execute("SELECT gender, preferred_gender, premium FROM users WHERE user_id=%s", (user_id,))
        user_info = cursor.fetchone()
        user_gender = user_info[0] if user_info else None
        user_preferred = user_info[1] if user_info else None
        is_premium = user_info[2] == 1 if user_info else False
        
        # FIRST: Try to find instant match (user searching but not in queue)
        cursor.execute("""
            SELECT user_id 
            FROM users 
            WHERE user_id <> %s 
                AND searching = 1 
                AND partner_id IS NULL
                AND user_id NOT IN (SELECT user_id FROM waiting_queue)
            LIMIT 1
        """, (user_id,))
        
        instant_partner = cursor.fetchone()
        
        if instant_partner:
            partner_id = instant_partner[0]
            logger.info(f"⚡ INSTANT MATCH: {user_id} <-> {partner_id}")
            
            cursor.execute("UPDATE users SET partner_id=%s, searching=0 WHERE user_id=%s", (partner_id, user_id))
            cursor.execute("UPDATE users SET partner_id=%s, searching=0 WHERE user_id=%s", (user_id, partner_id))
            db.commit()
            return partner_id
        
        # SECOND: Find partner from queue
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
            """
            params = (user_id, user_preferred)
        else:
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
            """
            params = (user_id,)
        
        cursor.execute(query, params)
        partner = cursor.fetchone()
        
        if not partner:
            logger.info(f"ℹ️ No partner in queue for user {user_id}")
            return None
        
        partner_id = partner[0]
        logger.info(f"🔍 Found partner in queue: {partner_id}")
        
        # Check partner status
        cursor.execute("SELECT partner_id, searching FROM users WHERE user_id=%s", (partner_id,))
        partner_check = cursor.fetchone()
        if partner_check and partner_check[0] is not None:
            logger.info(f"ℹ️ Partner {partner_id} already in chat, cleaning up...")
            cursor.execute("DELETE FROM waiting_queue WHERE user_id=%s", (partner_id,))
            db.commit()
            return None
        
        # Update both users
        cursor.execute("UPDATE users SET partner_id=%s, searching=0 WHERE user_id=%s", (partner_id, user_id))
        cursor.execute("UPDATE users SET partner_id=%s, searching=0 WHERE user_id=%s", (user_id, partner_id))
        cursor.execute("DELETE FROM waiting_queue WHERE user_id IN (%s, %s)", (user_id, partner_id))
        
        db.commit()
        logger.info(f"✅ Partner found from queue: {user_id} <-> {partner_id}")
        return partner_id
        
    except Exception as e:
        logger.error(f"❌ Find partner error: {e}")
        try:
            db.rollback()
        except:
            pass
        return None
    finally:
        cursor.close()
        return_connection(db)