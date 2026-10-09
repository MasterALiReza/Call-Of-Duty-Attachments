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

