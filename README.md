# Slackbot-with-chatgpt-dalle3-pdf-analyzer
## The best ChatGPT Plus features for your entire Slack Workspace
** NEWLY ADDED PDF UPload and chat function ***

## Overview
Welcome to the **Slack AI Assistant Bot**, a cutting-edge integration that brings the power of AI directly into your Slack workspace. This bot is designed to enhance productivity and streamline workflows by leveraging advanced AI capabilities, surpassing even Slack's internal AI offerings.

#### **Seamless Integration**: Built with Slack's Bolt framework and OpenAI's API, this bot integrates effortlessly into your existing Slack environment, enhancing your team's capabilities without disrupting workflows.
#### **User Interaction Logging**: Keep track of all interactions with detailed logs stored in Google Sheets, providing insights into usage patterns and helping improve team productivity.
-------
**Image Generation**: Utilize the latest DALL-E 3 model to create high-quality images from text prompts, directly within Slack. Perfect for brainstorming sessions, creative projects, and more.
   
![SCR-20250104-szaz](https://github.com/user-attachments/assets/74c3ae70-2ded-4d8b-ba66-526d1c71852e)
![SCR-20250104-szxq-2](https://github.com/user-attachments/assets/f6b3bcc3-1b51-4cf1-9f14-81b71d9092a0)
-------
#### **PDF Analysis**: 
Automatically process and analyze PDF documents, extracting key information and providing concise summaries. Ask questions about the content and receive direct, informative answers.
<img width="485" alt="SCR-20250104-tchp" src="https://github.com/user-attachments/assets/54ec6e27-e2aa-4252-b751-f75a453f9a66" />

- Upload PDFs direct to slack and ask it questions ala chatgpt plus
- Extract Text and insights from PDFs
_______
Other Features:
- Adjust message history in env file. Defaults to 30 mins and the previous 3 slack messages
- Maintain chat history to provide context for future prompts. Everything saved in slack
- Automatically converts OpenAI's markdown-formatted completions into Slack's markdown format, ensuring that AI-generated responses are always well-formatted and easy to read.
_______
## Getting Started
Before you can use the OpenAI ChatGPT Slackbot, you need to set up and configure your environment. 
1. Clone the Repository**: Get the latest version of the bot from GitHub.
2. **Configure Your Environment**: Set up your environment variables and API keys.
3. **Deploy to Slack**: Follow the setup instructions to integrate the bot into your Slack workspace.
4. **Enjoy Enhanced Productivity**: Start leveraging the full power of AI in your daily operations.

### Prerequisites

1. Python 3.6 and above
2. OpenAI Python Client (openai) 1.13.0 or later
3. Slack Bolt for Python (slack_bolt) 1.9.1 or later
4. Python-dotenv (python-dotenv) 0.19.1 or later

### Slack bot and App scopes
          "bot": [
                "app_mentions:read",
                "canvases:read",
                "canvases:write",
                "channels:history",
                "channels:join",
                "chat:write",
                "files:read",
                "files:write",
                "groups:history",
                "im:history",
                "im:read",
                "im:write",
                "incoming-webhook",
                "mpim:history",
                "users:read",
                "workflow.steps:execute"

            "bot_events": [
                "app_mention",
                "file_shared",
                "message.channels",
                "message.im"

### Installation

1. Clone the repository

```
git clone https://github.com/High-Tower80/Slackbot-with-chatgpt-dalle3-pdf-analyzer.git
```

2. Change into the project directory

```
cd slackbot-gpt-4
```

3. Install the required packages

```
pip install -r requirements.txt
```

### Configuration

1. Set up the Slack bot following the instructions [here](https://api.slack.com/start).
2. Obtain your API keys from Slack and OpenAI. You need the following:
   - Slack Bot Token
   - Slack App Token
   - OpenAI API Key
3. Set up your environment variables in a `.env` file. The variables you need to set are:
   - `SLACK_BOT_TOKEN`
   - `SLACK_APP_TOKEN`
   - `OPENAI_API_KEY`
   - `GPT_MODEL=gpt-4o #adjust as needed
   - GPT_SYSTEM_DESC="You are an AI assistant integrated into a bot application. Your primary goals are 	to: - Be helpful, knowledgeable, concise, and clear."

   - GPT_IMAGE_SIZE=1024x1024

   - HISTORY_EXPIRES_IN=900
   - HISTORY_SIZE=3
   - PDF_CONTEXT_EXPIRES_IN=3600
   - THREAD_HISTORY_EXPIRES_IN=1800
   - NOTION_TOKEN=your-notion-integration-token
   - NOTION_WIKI_DATA_SOURCE_ID=your-notion-data-source-id
   - WIKI_PUBLIC_BASE_URL=https://wiki.example.com
   - WIKI_INDEX_REFRESH_SECONDS=900

### Running the Slackbot

1. Run the Slackbot with the following command:

```
python main.py
```

## Usage
![Example Image](https://github.com/High-Tower80/Slack-chatgpt-bot-with-dall-e/blob/main/slackgpt%20sheets.png)

### Search the Company Wiki

The bot keeps an in-memory index of the Notion **Company Wiki** (titles, tags, and public links) and refreshes it in the background. Search it from Slack with:

```
/wiki wifi
```

or type `wiki: pto` in a DM or channel. Results use formatted public wiki links, not raw Notion URLs.

To enable wiki search:
1. Create a Notion internal integration and share the **Company Wiki** database with it.
2. Put the integration token in `.env` as `NOTION_TOKEN`.
3. Create a `/wiki` slash command on the Slack app (or push the updated `manifest.yml`) while Socket Mode stays enabled.
4. Optional env vars: `NOTION_WIKI_DATA_SOURCE_ID`, `NOTION_WIKI_DATABASE_ID`, `WIKI_PUBLIC_BASE_URL`, `WIKI_INDEX_REFRESH_SECONDS`.

______

### Generating Images with DALL-E

To generate an image with DALL-E, send a message in the following format:

```
image: Your image description here
```
![SCR-20250104-tjdx](https://github.com/user-attachments/assets/543f77ad-85b1-45dd-9cac-e837ae1aa309)


_______
## Notes
Why Choose This Bot?
**Superior AI Capabilities**: Outperforming Slack's native AI, this bot offers more advanced features and greater flexibility, tailored to meet the unique needs of your team.
**Enhanced Productivity**: By automating routine tasks and providing instant access to AI-powered tools, your team can focus on what truly matters.
**Customizable and Scalable**: Easily adapt the bot to fit your specific requirements, with the ability to scale as your team grows.

- This project is for demonstration purposes only and is not officially associated with OpenAI.
- This project does not include error handling for situations where the API keys are not set or incorrect. Please ensure that your API keys are correct before running the bot.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.


