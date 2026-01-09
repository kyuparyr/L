# Bot Features 🤖

## Core Features

### 1. **Multi-Account Management**
- Add multiple Instagram accounts
- Switch between accounts automatically with rotation
- Set cooldown periods between account usage

### 2. **Message Sending Modes**
- **DM Mode**: Send messages to individual users
- **GC Mode**: Send messages to Group Chats
- **Batch Sending**: Send multiple messages in sequence
- **Infinite Loop**: Continuously cycle through messages

### 3. **Message Parsing**
- Direct text input: `msg1 & msg2 & msg3`
- File upload: Upload `.txt` files with messages
- Multi-line support: Preserve ASCII art and formatted text
- Separator support: Use `&` or `and` to separate messages

### 4. **Authentication Methods**

#### Session Login (`/slogin`)
- Import existing Instagram session IDs
- Faster login, no password needed
- Perfect for bot accounts

#### Browser Login (`/plogin`)
- Playwright-based human-like login
- Full browser automation
- Support for 2FA and CAPTCHAs

#### Credentials Login (`/login`)
- Standard username/password login
- Automatic session file generation

### 5. **Advanced Features**

#### 🔄 **Auto Swipe Reply to Every Message** (NEW!)
- Bot automatically replies/swipes to every message in the group chat
- Heart reaction (❤️) added to existing messages
- Happens every 5 messages sent
- Maximum 10 messages replied per cycle

#### 💓 **Auto Self-Reaction** (NEW!)
- When bot's sent message receives a red heart (❤️) reaction
- Bot automatically reacts with heart to its own message
- Automatic engagement boost
- Happens immediately after message is sent

### 6. **Rate Limiting & Performance**
- Unlimited message sending mode (`MESSAGES_PER_SECOND=0`)
- Configurable thread/tab support (1-5 parallel tabs)
- Smart page reload every 60 seconds
- Retry logic with exponential backoff

### 7. **Account Pairing & Rotation**
- `/pair` - Create multi-account rotation setup
- Automatic account switching every N minutes
- Load balancing across accounts
- Cooldown period configuration

### 8. **Task Management**
- `/stop` - Stop current/all tasks
- `/task` - View running task status
- Persistent task storage
- Multi-task support (up to 5 simultaneous attacks)

### 9. **User Preferences**
- `/viewpref` - View your settings
- `/threads` - Set number of parallel tabs
- `/switch` - Configure account rotation time
- `/add` / `/remove` - Manage accounts

## Usage Examples

### Basic Message Sending
```
/attack → gc → Select Group → msg1 & msg2 & msg3
```

### With File Upload
```
/attack → gc → Select Group → Upload messages.txt
```

### Multi-Account Rotation
```
/pair → Add multiple accounts → /switch 10 → /attack
```

### Stop Sending
```
/stop <pid> or /stop all
```

## Configuration

### Environment Variables (`.env`)
```
TG_BOT_TOKEN=your_bot_token
OWNER_TG_ID=your_telegram_id
MESSAGES_PER_SECOND=0  # 0 = unlimited
```

### File Structure
```
/workspaces/bot/
├── spbot5.py              # Main bot
├── msg.py                 # Message sender (with new features!)
├── .env                   # Configuration
├── sessions/              # Instagram session files
├── config/                # Group/user configurations
└── README.md              # Documentation
```

## New Features in Detail

### Swipe Reply Feature
- **What it does**: Reacts with ❤️ to every message in the group chat
- **When it activates**: Every 5 messages the bot sends
- **Limit**: Maximum 10 messages replied per activation
- **Purpose**: Increase engagement and interaction in groups

### Auto Self-Reaction Feature
- **What it does**: When your message gets a ❤️ reaction, bot reacts back with ❤️
- **Timing**: Immediately after message is sent
- **Detection**: Monitors for red heart reactions
- **Purpose**: Boost message engagement and auto-respond to likes

## Commands

```
/help              - View all commands
/login             - Add account with credentials
/slogin            - Add account with session ID
/plogin            - Add account with browser login
/attack            - Start message attack
/stop              - Stop attack/task
/task              - View task status
/logout            - Remove account
/viewac            - View saved accounts
/setig             - Set default account
/pair              - Setup account rotation
/unpair            - Remove account pairing
/switch            - Set rotation time (minutes)
/threads           - Set parallel tabs (1-5)
/viewpref          - View preferences
/kill              - Force kill process
/users             - View authorized users
/flush             - Clear all data
/usg               - View usage
/add               - Add user
/remove            - Remove user
```

## Bot Status
✅ **Running and operational**
✅ **All features enabled**
✅ **Ready for use**

---
**Last Updated**: December 27, 2025
**Version**: 5.0 (with Swipe Reply & Auto Self-Reaction)
