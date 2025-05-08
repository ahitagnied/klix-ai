# 🪷 Klix Voice: AI Voice Calls

## 🦩 Set up

Begin by creating your environment file from our template:

```bash
cp .env.example .env
```

Fill out the following environment variables in your new `.env` file:

`OPENAI_API_KEY` - Your personal OpenAI API key  
`CARTESIA_API_KEY` - Your Cartesia API key for location services  
`DEEPGRAM_API_KEY` - Your Deepgram API key for speech recognition  
`TWILIO_ACCOUNT_SID` - Your Twilio Account SID for call handling  
`TWILIO_AUTH_TOKEN` - Your Twilio Auth Token for secure access  
`TWILIO_PHONE_NUMBER` - Your dedicated Twilio phone number  

## 🌐 Ngrok Configuration

Set up your ngrok tunnel to make your local server accessible:

```bash
ngrok http 8765 --subdomain <your_subdomain>
```

Replace `<your_subdomain>` with something unique like `lotus-ai`. You'll need to have ngrok installed and configured beforehand. Check out the [ngrok website](https://download.ngrok.com) for installation instructions.

## ☎️ Twilio Setup

Create a Twilio account at [https://www.twilio.com/try-twilio](https://www.twilio.com/try-twilio) if you don't already have one. Navigate to your Twilio phone number's configuration page and locate the "Voice Configuration" section.

In the "A call comes in" section, select "Webhook" from the dropdown menu and enter your ngrok URL (e.g., `http://<your_subdomain>.ngrok.io`). Make sure "HTTP POST" is selected, then save your configuration.

## 🔄 Streams Configuration

Copy the template streams file to create your own:

```bash
cp templates/streams.xml.template templates/streams.xml
```

Edit `templates/streams.xml` and replace `"wss://your-ngrok-url.ngrok.io/ws"` with your ngrok URL (without `https://`). Your final URL should look like: `wss://<your_subdomain>.ngrok.io/ws`.

## 🎴 Usage

Luna consists of three main components working together:

### 🖥️ Server Component

`server.py` is a FastAPI server handling WebSocket communication with Twilio and executing bot logic.

To run the server:

```bash
python server.py
```

In a separate terminal window:

```bash
uvicorn server:app --reload
```

### 🧠 Bot Logic

`bot.py` contains the core intelligence of Luna, including pipeline management and integration with various AI services. This component handles the conversation flow and decision-making processes.

### 📞 Outbound Caller

`caller.py` is a command-line tool for initiating outbound calls via the Twilio API.

To make an outbound call:

```bash
python caller.py +12345678910 --url <your_subdomain>.ngrok.io
```

Replace `+12345678910` with the target phone number and `<your_subdomain>.ngrok.io` with your ngrok URL. Ensure your `.env` file is properly configured for successful calls.

You may need to adjust the webhook URL in `templates/streams.xml` to match your deployment environment.