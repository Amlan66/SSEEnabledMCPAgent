# agent.py

import asyncio
import yaml
import sys
import argparse
from core.loop import AgentLoop
from core.session import MultiMCP

def log(stage: str, msg: str):
    """Simple timestamped console logger."""
    import datetime
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [{stage}] {msg}")


async def get_telegram_query(multi_mcp: MultiMCP):
    """Get query from Telegram using MCP tool"""
    try:
        log("telegram", "Waiting for Telegram message...")
        response = await multi_mcp.call_tool("get_telegram_query", {"timeout": 300})
        
        # Extract data from response
        if hasattr(response, 'content'):
            import json
            content = response.content[0].text if isinstance(response.content, list) else response.content.text
            data = json.loads(content) if isinstance(content, str) else content
        else:
            data = response
        
        if data.get("error"):
            log("telegram", f"Error: {data['error']}")
            return None, None, None
        
        return data.get("message"), data.get("chat_id"), data.get("username")
    except Exception as e:
        log("telegram", f"Failed to get telegram query: {e}")
        return None, None, None


async def send_telegram_reply(multi_mcp: MultiMCP, message: str, chat_id: int):
    """Send reply to Telegram using MCP tool"""
    try:
        log("telegram", "Sending reply to Telegram...")
        response = await multi_mcp.call_tool("send_telegram_reply", {
            "message": message,
            "chat_id": chat_id
        })
        log("telegram", "Reply sent successfully!")
    except Exception as e:
        log("telegram", f"Failed to send telegram reply: {e}")


async def main(mode: str = "cli"):
    print("=" * 60)
    print("🧠 Cortex-R Agent Ready")
    print(f"📍 Mode: {mode.upper()}")
    print("=" * 60)
    print()
    
    # Load MCP server configs from profiles.yaml
    with open("config/profiles.yaml", "r") as f:
        profile = yaml.safe_load(f)
        mcp_servers = profile.get("mcp_servers", [])

    multi_mcp = MultiMCP(server_configs=mcp_servers)
    log("agent", "Initializing MCP servers...")
    await multi_mcp.initialize()
    log("agent", "MCP servers initialized successfully")
    print()

    # Get user input based on mode
    if mode == "telegram":
        log("telegram", "📱 Telegram mode activated - waiting for messages from your group")
        print()
        
        # Continuous loop for telegram mode
        while True:
            try:
                user_input, chat_id, username = await get_telegram_query(multi_mcp)
                
                if not user_input:
                    log("telegram", "No valid message received, retrying...")
                    await asyncio.sleep(5)
                    continue
                
                log("telegram", f"📱 Query from @{username}: {user_input}")
                print()
                
            except KeyboardInterrupt:
                log("telegram", "Shutting down...")
                break
            except Exception as e:
                log("telegram", f"Error in telegram loop: {e}")
                await asyncio.sleep(5)
                continue
            
            # Process the query
            try:
                agent = AgentLoop(
                    user_input=user_input,
                    dispatcher=multi_mcp
                )
                
                final_response = await agent.run()
                clean_response = final_response.replace("FINAL_ANSWER:", "").strip()
                
                print()
                log("agent", f"Final Answer: {clean_response[:100]}...")
                print()
                
                # Send reply back to telegram
                await send_telegram_reply(multi_mcp, f"🤖 *Answer:*\n\n{clean_response}", chat_id)
                
                log("telegram", "Ready for next query...")
                print("-" * 60)
                print()
                
            except Exception as e:
                log("agent", f"Agent failed: {e}")
                error_msg = f"❌ Sorry, I encountered an error: {str(e)}"
                await send_telegram_reply(multi_mcp, error_msg, chat_id)
    
    else:  # CLI mode
        user_input = input("🧑 What do you want to solve today? → ")
        print()

        agent = AgentLoop(
            user_input=user_input,
            dispatcher=multi_mcp
        )

        try:
            final_response = await agent.run()
            print("\n" + "=" * 60)
            print("💡 Final Answer:")
            print("=" * 60)
            print(final_response.replace("FINAL_ANSWER:", "").strip())
            print("=" * 60)

        except Exception as e:
            log("fatal", f"Agent failed: {e}")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cortex-R AI Agent")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["cli", "telegram"],
        default="cli",
        help="Run mode: 'cli' for command line, 'telegram' for Telegram bot integration"
    )
    
    args = parser.parse_args()
    asyncio.run(main(mode=args.mode))


# Find the ASCII values of characters in INDIA and then return sum of exponentials of those values.
# How much Anmol singh paid for his DLF apartment via Capbridge? 
# What do you know about Don Tapscott and Anthony Williams?
# What is the relationship between Gensol and Go-Auto?
# which course are we teaching on Canvas LMS?
# Summarize this page: https://theschoolof.ai/
# What is the log value of the amount that Anmol singh paid for his DLF apartment via Capbridge? 
# Who is currently on top of the F1 driver standings?