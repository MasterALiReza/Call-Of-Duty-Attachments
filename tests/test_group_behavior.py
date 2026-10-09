import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, Message, User, Chat, CallbackQuery
from handlers.user.modules.navigation.main_menu import MainMenuHandler
from handlers.user.modules.categories.weapon_handler import WeaponHandler
from managers.channel_manager import require_channel_membership


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.users.is_admin = AsyncMock(return_value=False)
    db.settings.get_setting = AsyncMock(return_value="false")
    db.settings.get_ua_setting = AsyncMock(return_value="1")
    db.channels.get_active_channels = AsyncMock(return_value=[])
    db.channels.get_all = AsyncMock(return_value=[])
    db.cms.get_required_channels = AsyncMock(return_value=[])
    db.users.get_language = AsyncMock(return_value="fa")
    db.users.get_user_language = AsyncMock(return_value="fa")
    db.analytics.get_attachment_stats = AsyncMock(return_value={})
    db.analytics.track_attachment_view = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_group_start_does_not_send_reply_keyboard(mock_db):
    handler = MainMenuHandler(mock_db)

    chat = Chat(id=-1001234567890, type="supergroup")
    user = User(id=111, is_bot=False, first_name="TestUser")
    message = MagicMock(spec=Message)
    message.message_id = 99
    message.chat = chat
    message.from_user = user
    message.sender_chat = None
    message.reply_html = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.message = message

    context = MagicMock()
    context.args = []
    context.user_data = {}
    context.bot.username = "test_bot"
    context.bot_data = {"database": mock_db}

    # Calling start directly
    await handler.start(update, context)

    # Verify message was replied to with reply_to_message_id
    message.reply_html.assert_called_once()
    _, kwargs = message.reply_html.call_args
    assert kwargs.get("reply_to_message_id") == 99
    # Ensure reply_markup is InlineKeyboardMarkup, NOT ReplyKeyboardMarkup
    from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup
    assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)
    assert not isinstance(kwargs.get("reply_markup"), ReplyKeyboardMarkup)


@pytest.mark.asyncio
async def test_group_start_with_channel_sender(mock_db):
    handler = MainMenuHandler(mock_db)

    chat = Chat(id=-1001234567890, type="supergroup")
    channel_chat = Chat(id=-100987654321, type="channel", title="Wexort Channel")
    user = User(id=136817688, is_bot=False, first_name="Channel_Bot")

    message = MagicMock(spec=Message)
    message.message_id = 101
    message.chat = chat
    message.from_user = user
    message.sender_chat = channel_chat
    message.reply_html = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.message = message

    context = MagicMock()
    context.args = []
    context.user_data = {}
    context.bot.username = "test_bot"
    context.bot_data = {"database": mock_db}

    # Calling start directly
    await handler.start(update, context)

    # Should safely reply without Markdown parse error
    message.reply_html.assert_called_once()
    args, kwargs = message.reply_html.call_args
    assert "Wexort Channel" in args[0]
    assert kwargs.get("reply_to_message_id") == 101


@pytest.mark.asyncio
async def test_weapon_handler_suppresses_reply_keyboard_in_groups(mock_db):
    handler = WeaponHandler(mock_db)

    chat = Chat(id=-1001234567890, type="supergroup")
    user = User(id=111, is_bot=False, first_name="TestUser")

    query = MagicMock(spec=CallbackQuery)
    query.data = "wpn_AK-47"
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.reply_to_message = None
    query.message.reply_text = AsyncMock()
    query.message.edit_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.callback_query = query

    context = MagicMock()
    context.user_data = {"selected_mode": "br", "current_category": "AR"}
    context.bot_data = {"database": mock_db}

    mock_db.attachments.get_weapon_attachments = AsyncMock(return_value=[])

    # Calling show_weapon_menu
    await handler.show_weapon_menu(update, context)

    # In a group chat, reply_text with weapon reply keyboard must NOT be called
    query.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_button_ownership_isolation_in_groups(mock_db):
    chat = Chat(id=-1001234567890, type="supergroup")
    user_alice = User(id=111, is_bot=False, first_name="Alice")
    user_bob = User(id=222, is_bot=False, first_name="Bob")

    original_message = MagicMock(spec=Message)
    original_message.from_user = user_alice
    original_message.sender_chat = None

    bot_message = MagicMock(spec=Message)
    bot_message.reply_to_message = original_message

    query = MagicMock(spec=CallbackQuery)
    query.data = "categories"
    query.message = bot_message
    query.answer = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user_bob  # Bob clicks Alice's menu!
    update.callback_query = query

    context = MagicMock()
    context.bot_data = {"database": mock_db}
    context.bot.get_chat_member = AsyncMock()

    dummy_func = AsyncMock()
    decorated = require_channel_membership(dummy_func)

    await decorated(update, context)

    # Bob should receive a warning alert
    query.answer.assert_called_once()
    args, kwargs = query.answer.call_args
    assert kwargs.get("show_alert") is True
    assert "متعلق به کاربر دیگری است" in args[0]
    dummy_func.assert_not_called()


@pytest.mark.asyncio
async def test_button_ownership_allows_owner(mock_db):
    chat = Chat(id=-1001234567890, type="supergroup")
    user_alice = User(id=111, is_bot=False, first_name="Alice")

    original_message = MagicMock(spec=Message)
    original_message.from_user = user_alice
    original_message.sender_chat = None

    bot_message = MagicMock(spec=Message)
    bot_message.reply_to_message = original_message

    query = MagicMock(spec=CallbackQuery)
    query.data = "categories"
    query.message = bot_message
    query.answer = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user_alice  # Alice clicks her own menu
    update.callback_query = query

    context = MagicMock()
    context.bot_data = {"database": mock_db}
    context.bot.get_chat_member = AsyncMock()

    dummy_func = AsyncMock()
    decorated = require_channel_membership(dummy_func)

    await decorated(update, context)

    # Alice is allowed to proceed
    dummy_func.assert_called_once_with(update, context)


@pytest.mark.asyncio
async def test_button_ownership_allows_bot_admin(mock_db):
    chat = Chat(id=-1001234567890, type="supergroup")
    user_alice = User(id=111, is_bot=False, first_name="Alice")
    admin_user = User(id=999, is_bot=False, first_name="Admin")

    # DB confirms user 999 is bot admin
    mock_db.users.is_admin = AsyncMock(return_value=True)

    original_message = MagicMock(spec=Message)
    original_message.from_user = user_alice
    original_message.sender_chat = None

    bot_message = MagicMock(spec=Message)
    bot_message.reply_to_message = original_message

    query = MagicMock(spec=CallbackQuery)
    query.data = "categories"
    query.message = bot_message
    query.answer = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = admin_user  # Admin clicks Alice's menu
    update.callback_query = query

    context = MagicMock()
    context.bot_data = {"database": mock_db}
    context.bot.get_chat_member = AsyncMock()

    dummy_func = AsyncMock()
    decorated = require_channel_membership(dummy_func)

    await decorated(update, context)

    # Bot admin is allowed to proceed
    dummy_func.assert_called_once_with(update, context)


@pytest.mark.asyncio
async def test_group_channel_gate_shows_alert(mock_db):
    from managers.channel_manager import invalidate_user_cache
    invalidate_user_cache(88888)

    chat = Chat(id=-1001234567890, type="supergroup")
    user = User(id=88888, is_bot=False, first_name="NonMember")

    query = MagicMock(spec=CallbackQuery)
    query.data = "categories"
    query.message = MagicMock()
    query.answer = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.callback_query = query
    update.message = None

    # Database returns a required channel
    mock_db.cms.get_required_channels = AsyncMock(
        return_value=[{"channel_id": "-1001", "username": "test_channel"}]
    )

    context = MagicMock()
    context.bot_data = {"database": mock_db}
    # get_chat_member returns left status
    member_mock = MagicMock()
    member_mock.status = "left"
    context.bot.get_chat_member = AsyncMock(return_value=member_mock)

    dummy_func = AsyncMock()
    decorated = require_channel_membership(dummy_func)

    await decorated(update, context)

    # In groups, non-members get a modal alert without polluting the chat
    query.answer.assert_called_once()
    args, kwargs = query.answer.call_args
    assert kwargs.get("show_alert") is True
    assert "@test_channel" in args[0]
    dummy_func.assert_not_called()


@pytest.mark.asyncio
async def test_button_ownership_traverses_bot_reply_chain(mock_db):
    chat = Chat(id=-1001234567890, type="supergroup")
    user_alice = User(id=111, is_bot=False, first_name="Alice")
    bot_user = User(id=99999, is_bot=True, first_name="Bot")

    # Alice's original /start message
    user_message = MagicMock(spec=Message)
    user_message.from_user = user_alice
    user_message.sender_chat = None
    user_message.reply_to_message = None

    # M1: Bot text message replying to Alice
    bot_m1 = MagicMock(spec=Message)
    bot_m1.from_user = bot_user
    bot_m1.reply_to_message = user_message

    # M2: Bot photo message replying to M1
    bot_m2 = MagicMock(spec=Message)
    bot_m2.from_user = bot_user
    bot_m2.reply_to_message = bot_m1

    # Alice clicks back on M2
    query = MagicMock(spec=CallbackQuery)
    query.data = "all_AR__AK47"
    query.message = bot_m2
    query.answer = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user_alice
    update.callback_query = query

    context = MagicMock()
    context.bot.id = 99999
    context.bot_data = {"database": mock_db}
    context.bot.get_chat_member = AsyncMock()

    dummy_func = AsyncMock()
    decorated = require_channel_membership(dummy_func)

    await decorated(update, context)

    # Alice should be allowed since she is the root owner
    dummy_func.assert_called_once_with(update, context)


@pytest.mark.asyncio
async def test_group_back_message_removes_sticky_reply_keyboard(mock_db):
    from handlers.user.modules.navigation.main_menu import MainMenuHandler
    from telegram import ReplyKeyboardRemove

    handler = MainMenuHandler(mock_db)

    chat = Chat(id=-1001234567890, type="supergroup")
    user = User(id=111, is_bot=False, first_name="Alice")

    message = MagicMock(spec=Message)
    message.message_id = 555
    message.chat = chat
    message.from_user = user
    message.sender_chat = None
    message.reply_text = AsyncMock()
    message.reply_html = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.message = message

    context = MagicMock()
    context.args = []
    context.user_data = {}
    context.bot.username = "test_bot"
    context.bot_data = {"database": mock_db}

    await handler.back_msg(update, context)

    # In groups, back_msg must remove the reply keyboard selectively and then start()
    message.reply_text.assert_called_once()
    args, kwargs = message.reply_text.call_args
    assert isinstance(kwargs.get("reply_markup"), ReplyKeyboardRemove)
    assert kwargs.get("reply_to_message_id") == 555
    # And start was called which replied with HTML
    message.reply_html.assert_called_once()


@pytest.mark.asyncio
async def test_group_action_rate_limiter_basics():
    from core.security.rate_limiter import GroupActionRateLimiter

    limiter = GroupActionRateLimiter(cooldown_seconds=300.0, admin_cooldown_seconds=5.0)
    chat_a = -100111
    chat_b = -100222

    # First call allowed
    allowed, rem = await limiter.check_and_update(chat_a)
    assert allowed is True
    assert rem == 0

    # Immediate second call rate limited
    allowed2, rem2 = await limiter.check_and_update(chat_a)
    assert allowed2 is False
    assert 295 <= rem2 <= 300

    # Separate chat unaffected
    allowed_b, rem_b = await limiter.check_and_update(chat_b)
    assert allowed_b is True
    assert rem_b == 0

    # Admin cooldown is separate
    limiter.reset(chat_a)
    allowed_adm, _ = await limiter.check_and_update(chat_a, is_admin=True)
    assert allowed_adm is True
    # In admin window:
    allowed_adm2, rem_adm2 = await limiter.check_and_update(chat_a, is_admin=True)
    assert allowed_adm2 is False
    assert rem_adm2 <= 5

    # Dynamic set_cooldown and set_enabled
    limiter.set_cooldown(60.0)
    assert limiter.cooldown == 60.0

    limiter.set_enabled(False)
    allowed_dis, rem_dis = await limiter.check_and_update(chat_a)
    assert allowed_dis is True
    assert rem_dis == 0
    assert await limiter.get_remaining_async(chat_a) == 0


@pytest.mark.asyncio
async def test_group_action_rate_limiter_db_sync(mock_db):
    from core.security.rate_limiter import GroupActionRateLimiter

    mock_db.settings.get_setting.side_effect = lambda key, default=None: (
        "120" if key == "group_season_top_cooldown" else ("1" if key == "group_season_top_rl_enabled" else default)
    )

    limiter = GroupActionRateLimiter(cooldown_seconds=300.0)
    await limiter.ensure_initialized(mock_db)

    assert limiter.cooldown == 120.0
    assert limiter.enabled is True


@pytest.mark.asyncio
async def test_season_top_group_rate_limiting_flow(mock_db):
    from handlers.user.modules.attachments.season_handler import SeasonTopHandler
    from core.security.rate_limiter import group_season_top_limiter

    from core.container import get_container
    container = get_container()
    container.feedback_handler = MagicMock()
    container.feedback_handler.build_attachment_keyboard = MagicMock(return_value=[])

    mock_db.settings.get_setting = AsyncMock(side_effect=lambda key, default=None: (
        "300" if key == "group_season_top_cooldown" else ("1" if key == "group_season_top_rl_enabled" else default)
    ))

    group_season_top_limiter.reset()
    group_season_top_limiter.set_enabled(True)
    group_season_top_limiter.set_cooldown(300.0)

    handler = SeasonTopHandler(mock_db)
    mock_db.attachments.get_season_top_attachments = AsyncMock(return_value=[
        {
            "category": "AR",
            "weapon": "AK47",
            "attachment": {"id": 1, "name": "Meta Setup", "code": "AK-12345", "image": None},
        }
    ])

    group_chat = Chat(id=-100999888, type="supergroup")
    user_alice = User(id=111, is_bot=False, first_name="Alice")
    user_bob = User(id=222, is_bot=False, first_name="Bob")
    bot_user = User(id=99999, is_bot=True, first_name="Bot")

    # 1. Alice clicks season top mode BR
    msg_alice = MagicMock(spec=Message)
    msg_alice.from_user = bot_user
    msg_alice.reply_to_message = None
    msg_alice.sender_chat = None
    msg_alice.reply_text = AsyncMock()
    msg_alice.reply_photo = AsyncMock()

    query_alice = MagicMock(spec=CallbackQuery)
    query_alice.data = "season_top_mode_br"
    query_alice.from_user = user_alice
    query_alice.message = msg_alice
    query_alice.answer = AsyncMock()

    update_alice = MagicMock(spec=Update)
    update_alice.effective_chat = group_chat
    update_alice.effective_user = user_alice
    update_alice.callback_query = query_alice

    context = MagicMock()
    context.bot.id = 99999
    context.bot.get_chat_member = AsyncMock()
    context.bot_data = {"database": mock_db}
    context.user_data = {}

    await handler.season_top_media_with_mode(update_alice, context)

    # First request succeeded: media was sent
    query_alice.message.reply_text.assert_called()

    # 2. Bob immediately clicks season top mode MP in the same group
    msg_bob = MagicMock(spec=Message)
    msg_bob.from_user = bot_user
    msg_bob.reply_to_message = None
    msg_bob.sender_chat = None
    msg_bob.reply_text = AsyncMock()
    msg_bob.reply_photo = AsyncMock()

    query_bob = MagicMock(spec=CallbackQuery)
    query_bob.data = "season_top_mode_mp"
    query_bob.from_user = user_bob
    query_bob.message = msg_bob
    query_bob.answer = AsyncMock()

    update_bob = MagicMock(spec=Update)
    update_bob.effective_chat = group_chat
    update_bob.effective_user = user_bob
    update_bob.callback_query = query_bob

    await handler.season_top_media_with_mode(update_bob, context)

    # Bob's request was rejected via query.answer(show_alert=True)
    query_bob.answer.assert_called_once()
    answer_args, answer_kwargs = query_bob.answer.call_args
    assert answer_kwargs.get("show_alert") is True
    assert "برترهای فصل" in answer_args[0]
    # No message sent to the group!
    query_bob.message.reply_text.assert_not_called()
    query_bob.message.reply_photo.assert_not_called()

    # 3. Bob clicks season_top (mode selection menu) during active cooldown
    msg_bob_menu = MagicMock(spec=Message)
    msg_bob_menu.from_user = bot_user
    msg_bob_menu.reply_to_message = None
    msg_bob_menu.sender_chat = None

    query_bob_menu = MagicMock(spec=CallbackQuery)
    query_bob_menu.data = "season_top"
    query_bob_menu.from_user = user_bob
    query_bob_menu.message = msg_bob_menu
    query_bob_menu.answer = AsyncMock()

    update_bob_menu = MagicMock(spec=Update)
    update_bob_menu.effective_chat = group_chat
    update_bob_menu.effective_user = user_bob
    update_bob_menu.callback_query = query_bob_menu

    await handler.season_top_select_mode(update_bob_menu, context)

    # Rejection alert shown, menu not rendered
    query_bob_menu.answer.assert_called_once()
    assert query_bob_menu.answer.call_args[1].get("show_alert") is True

    # Reset limiter cleanup
    group_season_top_limiter.reset()


@pytest.mark.asyncio
async def test_admin_attachment_rate_limit_management(mock_db):
    from handlers.admin.modules.attachments.management_menu import AttachmentManagementHandler
    from core.security.rate_limiter import group_season_top_limiter

    handler = AttachmentManagementHandler(mock_db)
    handler.role_manager = MagicMock()
    handler.role_manager.get_user_permissions = AsyncMock(return_value=["manage_attachments_br"])
    handler.role_manager.is_super_admin = AsyncMock(return_value=True)

    admin_chat = Chat(id=999, type="private")
    admin_user = User(id=999, is_bot=False, first_name="Admin")

    query = MagicMock(spec=CallbackQuery)
    query.data = "admin_season_rate_limit"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_chat = admin_chat
    update.effective_user = admin_user
    update.callback_query = query

    context = MagicMock()
    context.user_data = {}

    # 1. Open season rate limit menu
    await handler.season_rate_limit_menu(update, context)
    query.edit_message_text.assert_called_once()
    text = query.edit_message_text.call_args[0][0]
    assert "محدودیت ارسال برترهای فصل" in text

    # 2. Toggle rate limit
    mock_db.settings.set_setting = AsyncMock(return_value=True)
    query_toggle = MagicMock(spec=CallbackQuery)
    query_toggle.data = "toggle_season_rl"
    query_toggle.answer = AsyncMock()
    query_toggle.edit_message_text = AsyncMock()
    update.callback_query = query_toggle

    await handler.toggle_season_rate_limit(update, context)
    mock_db.settings.set_setting.assert_called_once()
    assert mock_db.settings.set_setting.call_args[0][0] == "group_season_top_rl_enabled"

    # 3. Change cooldown to 600s
    mock_db.settings.set_setting.reset_mock()
    query_set = MagicMock(spec=CallbackQuery)
    query_set.data = "set_season_rl_600"
    query_set.answer = AsyncMock()
    query_set.edit_message_text = AsyncMock()
    update.callback_query = query_set

    await handler.set_season_rate_limit_seconds(update, context)
    mock_db.settings.set_setting.assert_called_once()
    assert mock_db.settings.set_setting.call_args[0][0] == "group_season_top_cooldown"
    assert mock_db.settings.set_setting.call_args[0][1] == "600"
    assert group_season_top_limiter.cooldown == 600.0

    # Cleanup
    group_season_top_limiter.set_cooldown(300.0)
    group_season_top_limiter.set_enabled(True)

