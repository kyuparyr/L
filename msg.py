import argparse
import os
import time
import re
import unicodedata
import json
import asyncio
from playwright.async_api import async_playwright

MOBILE_UA = "Mozilla/5.0 (Linux; Android 13; vivo V60) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"

MOBILE_VIEWPORT = {"width": 412, "height": 915}  # Typical Android phone size

LAUNCH_ARGS = [
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-extensions",
    "--disable-sync",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--mute-audio",
]

def sanitize_input(raw):
    """
    Fix shell-truncated input (e.g., when '&' breaks in CMD or bot execution).
    If input comes as a list (from nargs='+'), join it back into a single string.
    """
    if isinstance(raw, list):
        raw = " ".join(raw)
    return raw

def parse_messages(names_arg):
    """
    Robust parser for messages:
    - If names_arg is a .txt file, first try JSON-lines parsing (one JSON string per line, supporting multi-line messages).
    - If that fails, read the entire file content as a single block and split only on explicit separators '&' or 'and' (preserving newlines within each message for ASCII art).
    - For direct string input, treat as single block and split only on separators.
    This ensures ASCII art (multi-line blocks without separators) is preserved as a single message.
    """
    # Handle argparse nargs possibly producing a list
    if isinstance(names_arg, list):
        names_arg = " ".join(names_arg)

    content = None  
    is_file = isinstance(names_arg, str) and names_arg.endswith('.txt') and os.path.exists(names_arg)  

    if is_file:  
        # Try JSON-lines first (each line is a JSON-encoded string, possibly with \n for multi-line)  
        try:  
            msgs = []  
            with open(names_arg, 'r', encoding='utf-8') as f:  
                lines = [ln.rstrip('\n') for ln in f if ln.strip()]  # Skip empty lines  
            for ln in lines:  
                m = json.loads(ln)  
                if isinstance(m, str):  
                    msgs.append(m)  
                else:  
                    raise ValueError("JSON line is not a string")  
            if msgs:  
                # Normalize each message (preserve \n for art)  
                out = []  
                for m in msgs:  
                    #m = unicodedata.normalize("NFKC", m)  
                    #m = re.sub(r'[\u200B-\u200F\uFEFF\u202A-\u202E\u2060-\u206F]', '', m)  
                    out.append(m)  
                return out  
        except Exception:  
            pass  # Fall through to block parsing on any error  

        # Fallback: read entire file as one block for separator-based splitting  
        try:  
            with open(names_arg, 'r', encoding='utf-8') as f:  
                content = f.read()  
        except Exception as e:  
            raise ValueError(f"Failed to read file {names_arg}: {e}")  
    else:  
        # Direct string input  
        content = str(names_arg)  

    if content is None:  
        raise ValueError("No valid content to parse")  

    # Normalize content (preserve \n for ASCII art)  
    #content = unicodedata.normalize("NFKC", content)  
    #content = content.replace("\r\n", "\n").replace("\r", "\n")  
    #content = re.sub(r'[\u200B-\u200F\uFEFF\u202A-\u202E\u2060-\u206F]', '', content)  

    # Normalize ampersand-like characters to '&' for consistent splitting  
    content = (  
        content.replace('﹠', '&')  
        .replace('＆', '&')  
        .replace('⅋', '&')  
        .replace('ꓸ', '&')  
        .replace('︔', '&')  
    )  

    # Split only on explicit separators: '&' or the word 'and' (case-insensitive, with optional whitespace)  
    # This preserves multi-line blocks like ASCII art unless explicitly separated  
    pattern = r'\s*(?:&|\band\b)\s*'  
    parts = [part.strip() for part in re.split(pattern, content, flags=re.IGNORECASE) if part.strip()]  
    return parts

async def login(args, storage_path, headless):
    """
    Async login function to handle initial Instagram login and save storage state.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=LAUNCH_ARGS
            )
            context = await browser.new_context(
                user_agent=MOBILE_UA,
                viewport=MOBILE_VIEWPORT,
                is_mobile=True,
                has_touch=True,
                device_scale_factor=2,
                color_scheme="dark"
            )
            page = await context.new_page()
            try:
                print("Logging in to Instagram...")
                await page.goto("https://www.instagram.com/", timeout=60000)
                await page.wait_for_selector('input[name="username"]', timeout=30000)
                await page.fill('input[name="username"]', args.username)
                await page.fill('input[name="password"]', args.password)
                await page.click('button[type="submit"]')
                # Wait for successful redirect (adjust if needed for 2FA or errors)
                await page.wait_for_url("**/home**", timeout=60000)  # More specific to profile/home
                print("Login successful, saving storage state.")
                await context.storage_state(path=storage_path)
                return True
            except Exception as e:
                print(f"Login error: {e}")
                return False
            finally:
                await browser.close()
    except Exception as e:
        print(f"Unexpected login error: {e}")
        return False

async def init_page(page, url, dm_selector):
    """
    Initialize a single page by navigating to the URL with retries.
    Returns True if successful, False otherwise.
    """
    init_success = False
    for init_try in range(3):
        try:
            await page.goto("https://www.instagram.com/", timeout=60000)
            await page.goto(url, timeout=60000)
            await page.wait_for_selector(dm_selector, timeout=30000)
            init_success = True
            break
        except Exception as init_e:
            print(f"Tab for {url[:30]}... try {init_try+1}/3 failed: {init_e}")
            if init_try < 2:
                await asyncio.sleep(2)
    return init_success

async def reply_to_all_messages(page, duration=3):
    """
    SWIPE REPLY: React to incoming messages for a limited time.
    Duration: how many seconds to monitor (default 3s per message)
    """
    print(f"🔄 [REPLY_TO_ALL] Started - monitoring for {duration}s...")
    start_time = time.time()
    processed_messages = set()
    
    try:
        while time.time() - start_time < duration:
            try:
                # Find all messages in thread
                messages = await page.query_selector_all('div[role="article"]')
                if not messages:
                    messages = await page.query_selector_all('[data-testid="message-item"]')
                
                if messages:
                    # Process last 3 messages only
                    for msg in messages[-3:]:
                        msg_id = id(msg)
                        if msg_id in processed_messages:
                            continue
                        
                        try:
                            print(f"👀 [REPLY_TO_ALL] Processing message...")
                            # Hover to reveal action buttons
                            await msg.hover()
                            await asyncio.sleep(0.05)
                            
                            # Look for emoji/reaction button
                            react_btns = await msg.query_selector_all('button')
                            
                            for btn in react_btns:
                                label = await btn.get_attribute('aria-label') or ""
                                
                                # Look for reaction button
                                if any(x in label.lower() for x in ['react', 'emoji', 'like']):
                                    try:
                                        await btn.click()
                                        await asyncio.sleep(0.1)
                                        
                                        # Try to click heart emoji
                                        heart = await page.query_selector('button[aria-label*="❤"]')
                                        if heart:
                                            await heart.click()
                                            print(f"   ❤️ Heart reaction added!")
                                            processed_messages.add(msg_id)
                                            break
                                    except:
                                        continue
                        except:
                            continue
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                await asyncio.sleep(0.1)
                continue
        
        print(f"✅ [REPLY_TO_ALL] Completed after {duration}s")
        
    except Exception as e:
        print(f"❌ [REPLY_TO_ALL] Error: {e}")

async def react_message_with_hearts(page, msg_element, count=10):
    """
    React to a single message with multiple heart reactions.
    Adds up to 10 heart reactions to make it stand out.
    """
    reactions_added = 0
    try:
        for i in range(count):
            try:
                await msg_element.hover()
                await asyncio.sleep(0.03)
                
                reaction_btn = await msg_element.query_selector('button[aria-label*="react"]')
                if not reaction_btn:
                    reaction_btn = await msg_element.query_selector('div[role="button"]')
                
                if reaction_btn:
                    await reaction_btn.click()
                    await asyncio.sleep(0.03)
                    
                    # Select heart emoji
                    heart_btn = await page.query_selector('button[aria-label*="❤"]')
                    if heart_btn:
                        await heart_btn.click()
                        reactions_added += 1
                        await asyncio.sleep(0.02)
            except Exception as e:
                break
        
        return reactions_added
    except Exception as e:
        return reactions_added
async def check_and_self_react(page):
    """
    INSTANT SELF-REACT: Add 5-10 hearts to the message you just sent.
    """
    print(f"💓 [SELF_REACT] Started...")
    try:
        await asyncio.sleep(0.1)  # Brief delay for message to appear
        
        # Get last sent message
        messages = await page.query_selector_all('div[role="article"]')
        if not messages:
            messages = await page.query_selector_all('[data-testid="message-item"]')
        
        if messages:
            last_msg = messages[-1]
            print(f"💓 [SELF_REACT] Found message, adding hearts...")
            
            hearts_added = 0
            # Add 5 hearts
            for i in range(5):
                try:
                    await last_msg.hover()
                    await asyncio.sleep(0.05)
                    
                    # Find reaction button
                    react_btn = await last_msg.query_selector('button[aria-label*="Like"]')
                    if not react_btn:
                        react_btn = await last_msg.query_selector('button[aria-label*="react"]')
                    
                    if react_btn:
                        await react_btn.click()
                        await asyncio.sleep(0.08)
                        
                        # Click heart emoji
                        heart = await page.query_selector('button[aria-label*="❤"]')
                        if not heart:
                            heart = await page.query_selector('[aria-label*="❤"]')
                        
                        if heart:
                            await heart.click()
                            hearts_added += 1
                            print(f"   ❤️ +1 ({hearts_added}/5)")
                            await asyncio.sleep(0.08)
                        else:
                            break
                    else:
                        break
                except Exception as e:
                    break
            
            if hearts_added > 0:
                print(f"✅ [SELF_REACT] Done - {hearts_added} hearts added")
            return hearts_added > 0
        else:
            print(f"⚠️ [SELF_REACT] No messages found")
            return False
            
    except Exception as e:
        print(f"❌ [SELF_REACT] Error: {e}")
        return False

async def sender(tab_id, args, messages, context, page):
    """
    MAXIMUM AGGRESSION MODE: Fire messages as fast as possible.
    - 0.01s send delay (100 messages/minute)
    - Instant heart reactions (fire and forget)
    - Instant reply to all messages (fire and forget)
    - NO BLOCKING - all tasks run in parallel
    """
    dm_selector = 'div[role="textbox"][aria-label="Message"]'
    print(f"⚡ Tab {tab_id} MAXIMUM AGGRESSION - Firing at supersonic speed!")
    print(f"🔥 REPLY_TO_ALL_MESSAGES and SELF_REACT tasks launched in background!")
    current_page = page
    cycle_start = time.time()
    msg_index = 0
    
    while True:
        elapsed = time.time() - cycle_start
        if elapsed >= 60:
            try:
                await current_page.reload(timeout=60000)
                await current_page.wait_for_selector(dm_selector, timeout=30000)
            except Exception as reload_e:
                raise Exception(f"Tab {tab_id} reload failed")
            cycle_start = time.time()
            continue
        
        msg = messages[msg_index]
        send_success = False
        
        try:
            if not current_page.locator(dm_selector).is_visible():
                try:
                    await current_page.press(dm_selector, 'Enter')
                    await asyncio.sleep(0.01)
                except:
                    pass
                await asyncio.sleep(0.02)
                msg_index = (msg_index + 1) % len(messages)
                continue

            # SEND MESSAGE INSTANTLY - NO REACTIONS (reactions are for /engage command)
            await current_page.click(dm_selector)
            await current_page.fill(dm_selector, msg)
            await current_page.press(dm_selector, 'Enter')
            print(f"💬 {msg_index + 1} - Message sent!")
            
            send_success = True
        except Exception as send_e:
            pass
        
        if not send_success:
            raise Exception(f"Tab {tab_id} send failed")
        
        # MINIMUM DELAY - 0.01 seconds only
        await asyncio.sleep(0.01)
        msg_index = (msg_index + 1) % len(messages)

async def engage_only(storage_state, url):
    """
    ENGAGEMENT ONLY MODE: Continuously react and swipe reply to messages.
    No message sending - just pure engagement.
    Runs indefinitely until interrupted.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=LAUNCH_ARGS)
            
            # Load storage state to maintain session
            storage_json = {}
            try:
                with open(storage_state, 'r') as f:
                    storage_json = json.load(f)
            except:
                print(f"⚠️ Could not load storage state from {storage_state}")
                return
            
            context = await browser.new_context(
                storage_state=storage_json,
                user_agent=MOBILE_UA,
                viewport=MOBILE_VIEWPORT,
                is_mobile=True,
                has_touch=True
            )
            
            page = await context.new_page()
            
            print(f"🔥 ENGAGEMENT MODE - Connecting to {url}")
            try:
                await page.goto(url, timeout=30000)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"❌ Failed to load thread: {e}")
                return
            
            print(f"✅ Connected! Monitoring for messages...")
            message_count = 0
            
            # Continuous engagement loop
            while True:
                try:
                    # Check for messages
                    messages = await page.query_selector_all('div[role="article"]')
                    if not messages:
                        messages = await page.query_selector_all('[data-testid="message-item"]')
                    
                    if messages:
                        current_count = len(messages)
                        if current_count > message_count:
                            new_messages = current_count - message_count
                            print(f"\n📨 Found {new_messages} new message(s)! Total: {current_count}")
                            message_count = current_count
                            
                            # React to new messages
                            for msg in messages[-new_messages:]:
                                try:
                                    print(f"  👀 Reacting to message...")
                                    await msg.hover()
                                    await asyncio.sleep(0.05)
                                    
                                    # Find reaction button
                                    react_btns = await msg.query_selector_all('button')
                                    for btn in react_btns:
                                        label = await btn.get_attribute('aria-label') or ""
                                        if any(x in label.lower() for x in ['react', 'emoji', 'like']):
                                            await btn.click()
                                            await asyncio.sleep(0.1)
                                            
                                            # Add hearts
                                            for heart_num in range(3):
                                                heart = await page.query_selector('button[aria-label*="❤"]')
                                                if not heart:
                                                    heart = await page.query_selector('[aria-label*="❤"]')
                                                
                                                if heart:
                                                    await heart.click()
                                                    print(f"    ❤️ Heart {heart_num + 1}/3")
                                                    await asyncio.sleep(0.1)
                                                else:
                                                    break
                                            break
                                except Exception as react_e:
                                    print(f"  ⚠️ Reaction error: {react_e}")
                                    continue
                    
                    # Check every 2 seconds
                    await asyncio.sleep(2)
                    
                except KeyboardInterrupt:
                    print("\n\n🛑 Engagement stopped by user")
                    break
                except Exception as loop_e:
                    print(f"❌ Loop error: {loop_e}")
                    await asyncio.sleep(2)
            
    except Exception as e:
        print(f"❌ Engagement mode error: {e}")
    finally:
        try:
            await browser.close()
        except:
            pass

async def main():
    parser = argparse.ArgumentParser(description="Instagram DM Auto Sender using Playwright")
    parser.add_argument('--username', required=False, help='Instagram username (required for initial login)')
    parser.add_argument('--password', required=False, help='Instagram password (required for initial login)')
    parser.add_argument('--thread-url', required=True, help='Full Instagram direct thread URLs (comma-separated for multiple)')
    parser.add_argument('--names', nargs='+', required=True, help='Messages list, direct string, or .txt file (split on & or "and" for multiple; preserves newlines for art)')
    parser.add_argument('--headless', default='true', choices=['true', 'false'], help='Run in headless mode (default: true)')
    parser.add_argument('--storage-state', required=True, help='Path to JSON file for login state (persists session)')
    parser.add_argument('--tabs', type=int, default=1, help='Number of parallel tabs per thread URL (1-5, default 1)')
    args = parser.parse_args()
    args.names = sanitize_input(args.names)  # Handle bot/shell-truncated inputs

    thread_urls = [u.strip() for u in args.thread_url.split(',') if u.strip()]
    if not thread_urls:
        print("Error: No valid thread URLs provided.")
        return

    headless = args.headless == 'true'  
    storage_path = args.storage_state  
    do_login = not os.path.exists(storage_path)  

    if do_login:  
        if not args.username or not args.password:  
            print("Error: Username and password required for initial login.")  
            return  
        success = await login(args, storage_path, headless)
        if not success:
            return
    else:  
        print("Using existing storage state, skipping login.")  

    try:  
        messages = parse_messages(args.names)  
    except ValueError as e:  
        print(f"Error parsing messages: {e}")  
        return  

    if not messages:  
        print("Error: No valid messages provided.")  
        return  

    print(f"Parsed {len(messages)} messages.")  

    tabs = min(max(args.tabs, 1), 5)  
    total_tabs = len(thread_urls) * tabs
    print(f"Using {tabs} tabs per URL across {len(thread_urls)} URLs (total: {total_tabs} tabs).")  

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=LAUNCH_ARGS
        )
        context = await browser.new_context(
            storage_state=storage_path,
            user_agent=MOBILE_UA,
            viewport=MOBILE_VIEWPORT,
            is_mobile=True,
            has_touch=True,
            device_scale_factor=2,
            color_scheme="dark"
        )
        dm_selector = 'div[role="textbox"][aria-label="Message"]'
        pages = []
        tasks = []
        try:
            while True:
                # Close previous pages and cancel tasks if any
                for page in pages:
                    try:
                        await page.close()
                    except Exception:
                        pass
                pages = []
                for task in tasks:
                    try:
                        task.cancel()
                    except Exception:
                        pass
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []

                # Create all pages first
                page_urls = []
                for url in thread_urls:
                    for i in range(tabs):
                        page = await context.new_page()
                        page_urls.append((page, url))

                # Initialize all pages concurrently
                init_tasks = [asyncio.create_task(init_page(page, url, dm_selector)) for page, url in page_urls]
                init_results = await asyncio.gather(*init_tasks, return_exceptions=True)

                # Filter successful initializations
                for idx, result in enumerate(init_results):
                    page, url = page_urls[idx]
                    if isinstance(result, Exception) or not result:
                        print(f"Tab for {url} failed to initialize after 3 tries, skipping.")
                        try:
                            await page.close()
                        except:
                            pass
                    else:
                        pages.append(page)
                        print(f"Tab {len(pages)} ready for {url[:50]}...")

                if not pages:
                    print("No tabs could be initialized, exiting.")
                    return

                actual_tabs = len(pages)
                tasks = [asyncio.create_task(sender(j + 1, args, messages, context, pages[j])) for j in range(actual_tabs)]
                print(f"Starting {actual_tabs} tab(s) in infinite message loop. Press Ctrl+C to stop.")

                pending = set(tasks)
                while pending:
                    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        if task.exception():
                            exc = task.exception()
                            print(f"Tab task raised exception: {exc}")
                            # Cancel remaining tasks
                            for t in list(pending):
                                t.cancel()
                            await asyncio.gather(*pending, return_exceptions=True)
                            pending.clear()
                            break
                    else:
                        continue
                    break  # If we broke due to exception, exit inner while
        except KeyboardInterrupt:
            print("\nStopping all tabs...")
        finally:
            for page in pages:
                try:
                    await page.close()
                except Exception:
                    pass
            await context.close()
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())