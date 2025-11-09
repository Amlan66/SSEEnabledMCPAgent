"""
MCP SSE Server for Telegram Integration
Exposes Telegram bot functionality as MCP tools via SSE transport
"""

import os
import sys
import asyncio
from typing import Optional
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("telegram-integration")

# Global message queue and telegram app
message_queue: asyncio.Queue = asyncio.Queue()
telegram_app: Optional[Application] = None
bot_active = False


async def telegram_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming telegram messages and add them to queue"""
    global bot_active
    
    if not update.message or not update.message.text:
        return
    
    message = update.message.text
    chat_id = update.effective_chat.id
    username = update.effective_user.username or update.effective_user.first_name or "Unknown"
    message_id = update.message.message_id
    
    logger.info(f"📱 Received message from {username} (chat_id: {chat_id}): {message}")
    
    # Add to queue
    await message_queue.put({
        "message": message,
        "chat_id": chat_id,
        "username": username,
        "message_id": message_id
    })
    
    # Send acknowledgment
    try:
        await update.message.reply_text("🤖 Processing your request... Please wait.")
        bot_active = True
    except Exception as e:
        logger.error(f"Error sending acknowledgment: {e}")


@mcp.tool()
async def get_telegram_query(timeout: int = 300, ctx: Context = None) -> dict:
    """
    Wait for and retrieve the next Telegram message from the queue.
    
    Args:
        timeout: Maximum seconds to wait for a message (default: 300)
    
    Returns:
        Dictionary with message, chat_id, username, and message_id
    """
    try:
        logger.info(f"⏳ Waiting for Telegram message (timeout: {timeout}s)...")
        data = await asyncio.wait_for(message_queue.get(), timeout=timeout)
        logger.info(f"✅ Retrieved message: {data['message'][:50]}...")
        return data
    except asyncio.TimeoutError:
        logger.warning("⏰ Timeout waiting for Telegram message")
        return {
            "message": None,
            "chat_id": None,
            "username": None,
            "error": "Timeout: No message received within timeout period"
        }
    except Exception as e:
        logger.error(f"❌ Error getting telegram query: {e}")
        return {
            "message": None,
            "chat_id": None,
            "username": None,
            "error": str(e)
        }


@mcp.tool()
async def send_telegram_reply(message: str, chat_id: int, ctx: Context = None) -> dict:
    """
    Send a reply message back to the Telegram chat.
    
    Args:
        message: The message text to send
        chat_id: The Telegram chat ID to send the message to
    
    Returns:
        Status dictionary indicating success or failure
    """
    global telegram_app
    
    if not telegram_app:
        error_msg = "Telegram bot is not initialized"
        logger.error(f"❌ {error_msg}")
        return {"success": False, "error": error_msg}
    
    try:
        logger.info(f"📤 Sending reply to chat_id {chat_id}: {message[:100]}...")
        
        # Split long messages if needed (Telegram has 4096 char limit)
        max_length = 4000
        if len(message) > max_length:
            # Split into chunks
            chunks = [message[i:i+max_length] for i in range(0, len(message), max_length)]
            for i, chunk in enumerate(chunks):
                if i > 0:
                    await asyncio.sleep(0.5)  # Small delay between chunks
                await telegram_app.bot.send_message(
                    chat_id=chat_id,
                    text=f"[Part {i+1}/{len(chunks)}]\n\n{chunk}",
                    parse_mode='Markdown'
                )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )
        
        logger.info("✅ Reply sent successfully")
        return {"success": True, "message": "Reply sent successfully"}
    
    except Exception as e:
        error_msg = f"Failed to send telegram reply: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return {"success": False, "error": error_msg}


@mcp.tool()
async def check_telegram_status() -> dict:
    """
    Check if Telegram bot is active and ready to receive messages.
    
    Returns:
        Status dictionary with bot information
    """
    global telegram_app, bot_active
    
    return {
        "bot_initialized": telegram_app is not None,
        "bot_active": bot_active,
        "queue_size": message_queue.qsize(),
        "status": "ready" if telegram_app and bot_active else "waiting"
    }


async def initialize_telegram_bot():
    """Initialize the Telegram bot application"""
    global telegram_app
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ TELEGRAM_BOT_TOKEN not set in .env file!")
        logger.error("Please create a .env file with your bot token from BotFather")
        return None
    
    logger.info("🤖 Initializing Telegram bot...")
    
    # Create the Application
    telegram_app = Application.builder().token(bot_token).build()
    
    # Add message handler for all text messages
    telegram_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_message_handler)
    )
    
    logger.info("✅ Telegram bot initialized successfully!")
    logger.info("📱 Bot is now listening for messages in your Telegram group")
    
    return telegram_app


async def run_telegram_bot():
    """Start the Telegram bot polling"""
    global telegram_app
    
    if not telegram_app:
        telegram_app = await initialize_telegram_bot()
    
    if telegram_app:
        logger.info("🚀 Starting Telegram bot polling...")
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling(drop_pending_updates=True)
        logger.info("✅ Telegram bot is now running and listening for messages")


async def stop_telegram_bot():
    """Stop the Telegram bot"""
    global telegram_app
    
    if telegram_app:
        logger.info("🛑 Stopping Telegram bot...")
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
        logger.info("✅ Telegram bot stopped")


def start_telegram_bot_in_background():
    """Run Telegram bot in a separate thread"""
    async def run_bot():
        await run_telegram_bot()
        # Keep the bot running
        while True:
            await asyncio.sleep(1)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_bot())
    except Exception as e:
        logger.error(f"Telegram bot thread error: {e}")
    finally:
        loop.close()


if __name__ == "__main__":
    # Check if bot token is set
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not set!")
        print()
        print("Please follow these steps:")
        print("1. Create a .env file in the project root")
        print("2. Add: TELEGRAM_BOT_TOKEN=your_token_from_botfather")
        print("3. Get token from @BotFather on Telegram")
        print()
        sys.exit(1)
    
    print("=" * 60)
    print("🤖 MCP TELEGRAM SSE SERVER")
    print("=" * 60)
    print()
    print("✅ Bot token found")
    print()
    
    # Start Telegram bot in background thread
    print("🤖 Starting Telegram bot in background...")
    import threading
    bot_thread = threading.Thread(target=start_telegram_bot_in_background, daemon=True)
    bot_thread.start()
    
    # Give bot a moment to initialize
    import time
    time.sleep(3)
    print("✅ Telegram bot thread started!")
    print()
    
    print("🚀 Starting MCP SSE server on http://localhost:8000")
    print("📡 SSE endpoint: http://localhost:8000/sse")
    print()
    print("📱 Registering tools:")
    print("   - get_telegram_query")
    print("   - send_telegram_reply")
    print("   - check_telegram_status")
    print()
    print("📱 You can now send messages in your Telegram group!")
    print()
    print("To use:")
    print("1. Open another terminal")
    print("2. Run: python agent.py --mode telegram")
    print("3. Wait for 'SSE connection established' message")
    print("4. Send messages in your Telegram group")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    try:
        # Run MCP server (blocking)
        logger.info("Starting FastMCP SSE server...")
        mcp.run(transport="sse")
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        print("✅ Server stopped")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        import traceback
        traceback.print_exc()

