import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from core.database.database_pg import DatabasePostgres

async def seed_faqs():
    print("Connecting to database...")
    db = DatabasePostgres()
    
    # Default FAQs - 5 for FA, 5 for EN
    # Signature: add_faq(question, answer, category, lang)
    defaults = [
        # FA
        {
            "question": "چگونه از ربات استفاده کنم؟",
            "answer": "از منوی اصلی، **مود بازی** (بتل رویال یا مولتی پلیر) را انتخاب کنید. سپس نوع تفنگ (مثلاً Assault) و خود تفنگ را انتخاب کنید تا بهترین اتچمنت‌ها برای شما نمایش داده شود.",
            "category": "general",
            "lang": "fa"
        },
        {
            "question": "چگونه اتچمنت خود را ثبت کنم؟",
            "answer": "از منوی اصلی وارد بخش **🎮 اتچمنت کاربران** شوید و دکمه **📤 ارسال اتچمنت** را بزنید. سپس طبق راهنما، نام، عکس و کد اتچمنت خود را بفرستید تا پس از تایید در ربات قرار گیرد.",
            "category": "user_content",
            "lang": "fa"
        },
        {
            "question": "چرا اتچمنت من هنوز تایید نشده؟",
            "answer": "همه اتچمنت‌های ارسالی کاربران باید توسط **ادمین‌ها** بررسی شوند تا از کیفیت آن‌ها اطمینان حاصل شود. این فرآیند ممکن است کمی زمان ببرد. پس از بررسی، نتیجه به شما اطلاع داده می‌شود.",
            "category": "user_content",
            "lang": "fa"
        },
        {
            "question": "چگونه با پشتیبانی تماس بگیرم؟",
            "answer": "از منوی اصلی دکمه **📞 تماس با ما** را انتخاب کنید. می‌توانید **تیکت** ثبت کنید، پیام مستقیم بفرستید یا پیشنهاد/انتقاد خود را مطرح کنید.",
            "category": "support",
            "lang": "fa"
        },
        {
            "question": "سلاح‌های متا کدامند؟",
            "answer": "در بخش انتخاب سلاح، تفنگ‌هایی که با علامت 🔥 مشخص شده‌اند، معمولاً جزو متای سیزن جاری هستند و قدرت بالایی دارند.",
            "category": "gameplay",
            "lang": "fa"
        },
        # EN
        {
            "question": "How do I use the bot?",
            "answer": "Select your **Game Mode** (Battle Royale or Multiplayer) from the main menu. Then choose a weapon category and the specific weapon to see the best recommended attachments/gunsmiths.",
            "category": "general",
            "lang": "en"
        },
        {
            "question": "How can I submit my own loadout?",
            "answer": "Go to **🎮 User Attachments** in the main menu and click **📤 Submit Attachment**. Follow the prompts to send your loadout name, screenshot, and code.",
            "category": "user_content",
            "lang": "en"
        },
        {
            "question": "Why is my submission pending?",
            "answer": "All user submissions are reviewed by **admins** manually to ensure quality. This process takes some time. You will receive a notification once your loadout is approved or rejected.",
            "category": "user_content",
            "lang": "en"
        },
        {
            "question": "How to contact support?",
            "answer": "Select **📞 Contact Us** from the main menu. You can open a **Ticket**, send a direct message, or leave feedback.",
            "category": "support",
            "lang": "en"
        },
        {
            "question": "Which weapons are META?",
            "answer": "In the weapon selection menu, weapons marked with a 🔥 icon are usually considered the current season's META (Most Effective Tactics Available).",
            "category": "gameplay",
            "lang": "en"
        }
    ]
    
    count = 0
    print(f"Attempting to seed {len(defaults)} FAQs...")
    
    # Check schema first using direct query to ensure exception is raised if column missing
    try:
        # Probe for 'language' column
        db.execute_query("SELECT language FROM faqs LIMIT 1;")
    except Exception as e:
        error_str = str(e)
        # Check for specific postgres error
        if "UndefinedColumn" in error_str or "column" in error_str:
            print("(!) Schema mismatch detected (missing 'language' column).")
            print("(!) Attempting to DROP and RECREATE 'faqs' table...")
            try:
                # DROP
                db.execute_query("DROP TABLE IF EXISTS faqs CASCADE;")
                print("Table dropped.")
                
                # CREATE
                create_sql_fixed = """
                CREATE TABLE IF NOT EXISTS faqs (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    category VARCHAR(50) DEFAULT 'general',
                    views INTEGER DEFAULT 0,
                    helpful_count INTEGER NOT NULL DEFAULT 0,
                    not_helpful_count INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    language VARCHAR(8) NOT NULL DEFAULT 'fa',
                    UNIQUE(question, language)
                );
                CREATE INDEX IF NOT EXISTS idx_faqs_category ON faqs (category) WHERE is_active = TRUE;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_faqs_question_language ON faqs (question, language);
                """
                
                db.execute_query(create_sql_fixed)
                print("Table recreated with correct schema (using 'language' column).")
            except Exception as e2:
                print(f"(X) Failed to reset table: {e2}")
                return

    # Now loop real seeding
    count = 0
    
    print("Starting seeding process...")
    for faq in defaults:
        try:
            # We use direct query to ensure we use 'language'
            query = """
                INSERT INTO faqs (question, answer, category, language)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (question, language) DO NOTHING
            """
            result = db.execute_query(query, (faq['question'], faq['answer'], faq['category'], faq['lang']))
            print(f"(+) Added: {faq['question'][:20]}... ({faq['lang']})")
            count += 1
            
        except Exception as e:
            print(f"(X) Error adding item: {e}")

    print(f"Summary: Successfully processed {count} FAQs.")

if __name__ == "__main__":
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    asyncio.run(seed_faqs())
