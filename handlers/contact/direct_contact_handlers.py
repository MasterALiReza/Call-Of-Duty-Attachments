from core.context import CustomContext
"""
ماژول مدیریت تماس مستقیم برای پنل ادمین
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.admin.admin_states import ADMIN_MENU, DIRECT_CONTACT_NAME, DIRECT_CONTACT_LINK


class DirectContactHandlers:
    """کلاس handlers مدیریت تماس مستقیم"""
    
    def __init__(self, db, role_manager):
        self.db = db
        self.role_manager = role_manager
    
    async def admin_direct_contact_menu(self, update: Update, context: CustomContext):
        """منوی مدیریت تماس مستقیم"""
        query = update.callback_query
        await query.answer()
        
        # دریافت تنظیمات فعلی
        enabled = await self.db.get_setting('direct_contact_enabled', 'true')
        contact_name = await self.db.get_setting('direct_contact_name', '💬 تماس مستقیم')
        contact_link = await self.db.get_setting('direct_contact_link', 'https://t.me/YourSupportChannel')
        
        status_text = "🟢 فعال" if enabled.lower() == 'true' else "🔴 غیرفعال"
        
        text = f"""💬 **مدیریت تماس مستقیم**

📊 **وضعیت فعلی:**
├─ وضعیت: {status_text}
├─ نام دکمه: {contact_name}
└─ لینک: `{contact_link}`

این قسمت به کاربران امکان دسترسی مستقیم به کانال/اکانت پشتیبانی شما را می‌دهد."""
        
        keyboard = [
            [InlineKeyboardButton("📝 تغییر نام دکمه", callback_data="dc_change_name"),
             InlineKeyboardButton("🔗 تغییر لینک", callback_data="dc_change_link")],
        ]
        
        if enabled.lower() == 'true':
            keyboard.append([InlineKeyboardButton("🔴 غیرفعال کردن", callback_data="dc_disable")])
        else:
            keyboard.append([InlineKeyboardButton("🟢 فعال کردن", callback_data="dc_enable")])
        
        keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_tickets")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return ADMIN_MENU
    
    async def direct_contact_toggle(self, update: Update, context: CustomContext):
        """فعال/غیرفعال کردن تماس مستقیم"""
        query = update.callback_query
        await query.answer()
        
        action = query.data.split('_')[-1]  # enable یا disable
        new_status = 'true' if action == 'enable' else 'false'
        
        success = await self.db.set_setting(
            'direct_contact_enabled', 
            new_status,
            'وضعیت فعال/غیرفعال تماس مستقیم',
            'contact',
            update.effective_user.id
        )
        
        if success:
            status_text = "فعال" if action == 'enable' else "غیرفعال"
            await query.answer(f"✅ تماس مستقیم {status_text} شد", show_alert=True)
        else:
            await query.answer("❌ خطا در تغییر وضعیت", show_alert=True)
        
        # بازگشت به منوی مدیریت
        return await self.admin_direct_contact_menu(update, context)
    
    async def direct_contact_change_name_start(self, update: Update, context: CustomContext):
        """شروع تغییر نام دکمه"""
        query = update.callback_query
        await query.answer()
        
        current_name = await self.db.get_setting('direct_contact_name', '💬 تماس مستقیم')
        
        text = f"""📝 **تغییر نام دکمه تماس مستقیم**

نام فعلی: `{current_name}`

لطفاً نام جدید برای دکمه تماس مستقیم را وارد کنید:

**نکته:** می‌تونید از emoji استفاده کنید (مثل 💬 یا 📞)"""
        
        keyboard = [[InlineKeyboardButton("❌ لغو", callback_data="adm_direct_contact")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return DIRECT_CONTACT_NAME
    
    async def direct_contact_name_received(self, update: Update, context: CustomContext):
        """دریافت نام جدید"""
        new_name = update.message.text.strip()
        
        if len(new_name) < 3:
            await update.message.reply_text("❌ نام دکمه باید حداقل 3 کاراکتر باشد.")
            return DIRECT_CONTACT_NAME
        
        if len(new_name) > 30:
            await update.message.reply_text("❌ نام دکمه نباید بیش از 30 کاراکتر باشد.")
            return DIRECT_CONTACT_NAME
        
        success = await self.db.set_setting(
            'direct_contact_name', 
            new_name,
            'نام دکمه تماس مستقیم',
            'contact',
            update.effective_user.id
        )
        
        if success:
            await update.message.reply_text(f"✅ نام دکمه به `{new_name}` تغییر یافت.", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ خطا در تغییر نام")
        
        # بازگشت به منوی مدیریت
        return ADMIN_MENU
    
    async def direct_contact_change_link_start(self, update: Update, context: CustomContext):
        """شروع تغییر لینک"""
        query = update.callback_query
        await query.answer()
        
        current_link = await self.db.get_setting('direct_contact_link', 'https://t.me/YourSupportChannel')
        
        text = f"""🔗 **تغییر لینک تماس مستقیم**

لینک فعلی: `{current_link}`

لطفاً لینک جدید را وارد کنید:

**مثال‌های معتبر:**
• `https://t.me/YourChannel`
• `https://t.me/YourBot`
• `https://t.me/+ABC123xyz`

**نکته:** لینک باید با https://t.me/ شروع شود."""
        
        keyboard = [[InlineKeyboardButton("❌ لغو", callback_data="adm_direct_contact")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return DIRECT_CONTACT_LINK
    
    async def direct_contact_link_received(self, update: Update, context: CustomContext):
        """دریافت لینک جدید"""
        new_link = update.message.text.strip()
        
        # اعتبارسنجی لینک تلگرام
        if not new_link.startswith('https://t.me/'):
            await update.message.reply_text("❌ لینک باید با `https://t.me/` شروع شود.")
            return DIRECT_CONTACT_LINK
        
        if len(new_link) < 15:
            await update.message.reply_text("❌ لینک خیلی کوتاه است.")
            return DIRECT_CONTACT_LINK
        
        success = await self.db.set_setting(
            'direct_contact_link', 
            new_link,
            'لینک تماس مستقیم',
            'contact', 
            update.effective_user.id
        )
        
        if success:
            await update.message.reply_text(f"✅ لینک تماس مستقیم به `{new_link}` تغییر یافت.", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ خطا در تغییر لینک")
        
        # بازگشت به منوی مدیریت
        return ADMIN_MENU
