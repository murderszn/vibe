<div align="center">
  <img src="vibe.png" alt="Vibe the Cool Cat" width="300"/>
  <h1>Vibe - The Educational Discord Bot</h1>

  <p>
    <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/Discord.py-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord.py">
    <img src="https://img.shields.io/badge/Anthropic_Claude-D97757?style=for-the-badge&logo=anthropic&logoColor=white" alt="Anthropic">
    <img src="https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge" alt="Status">
  </p>
</div>

## 📌 About Vibe

**Vibe** is a cool-cat persona, AI-powered Discord bot designed specifically to support middle school education and homeschooling. Leveraging the deep knowledge of Anthropic's Claude framework combined with Discord's real-time communication platform, Vibe serves both as an engaging tutor for students and an administrative assistant for server owners.

Vibe uses advanced **tool execution capabilities** to physically act upon the Discord server. Instead of just answering questions, Vibe can create roles, rename channels, issue timeouts, or purge messages when instructed by recognized admins.

---

## ✨ Features

- **Educational AI Tutor:** Highly encouraging and knowledgeable about middle-school subjects, offering easy-to-understand explanations with a laid-back persona.
- **Smart Conversations:** Retains conversation context (up to 10 previous messages per channel) to simulate natural chatting. Contextualizes the experience by knowing users' names and server roles.
- **Agentic Administration Tools:** Authorized users (specifically those with an `Admin` role) can ask Vibe to manage the server. Vibe utilizes Discord tools to successfully:
  - Kick, ban, unban, and timeout members
  - Create and delete voice/text channels
  - Create, assign, and remove roles
  - Set channel slowmode and delete (purge) bulk messages
- **Built-in Rate Limiting:** Enforces a 5-second cooldown per user to prevent API spam and rate-limit exhaustion.
- **Seamless Integrations:** Correctly handles Discord's 2000 character limit by automatically chunking and sending larger responses securely.

---

## 🚀 How to Interact with Vibe

Vibe is programmed to be unobtrusive and ignores general chatter in the server. 

To summon Vibe, you must **`@mention`** him explicitly in a text channel or speak to him via **Direct Message**.

### Built-in Commands:
- `@Vibe [your question]` - Chat with Vibe.
- `!help` - Displays the bot's features and commands.
- `!reset` - Clears the recent conversation history for the current channel to start fresh.

---

## 🛠️ Setup & Installation

### Prerequisites
1. **Python 3.8+** installed on your machine.
2. A Discord application bot from the [Discord Developer Portal](https://discord.com/developers/applications).
   - Ensure the **Message Content Intent** and **Server Members Intent** are enabled.
3. An API key from [Anthropic](https://console.anthropic.com/).

### Installation

1. **Clone the repository** or download the files.
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure your `.env` file** in the root directory:
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```
4. **Run the bot**:
   ```bash
   python3 bot.py
   ```

### Admin Configuration
In order to use the server management tools (like kicking members or deleting channels), the user requesting the action **must** have a role specifically named `Admin`. Vibe logs all administrative actions automatically to a channel named `bot-logs`. Ensure this channel exists in your server so Vibe can report its actions! 

---
<div align="center">
  <i>Stay cool and keep learning! 🐱</i>
</div>
