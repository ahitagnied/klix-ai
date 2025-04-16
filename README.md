# klix-ai
<p align="center">
  <img src="assets/klix.png" alt="Alt text" width="100"/>
</p>

Klix is a real-time AI voice agent evaluation system that transcribes calls, applies predefined feedback criteria, and accelerates bug detection. Inspired by Fixa’s (YC F24) approach to performance analysis, Klix streamlines how you monitor and refine voice-based user interactions.

## Features

*   **Real-time Transcription:** Transcribes calls in real-time using OpenAI's Whisper API.
*   **AI-Powered Feedback:**  Provides feedback on agent performance based on predefined criteria.
*   **Bug Detection:** Helps identify and pinpoint bugs in the voice agent system quickly.
*   **Twilio Integration:** Leverages Twilio for handling voice calls and media streams.
*   **OpenAI Integration:** Uses OpenAI's GPT-4 for natural language processing and AI responses.
*   **Wave File Recording:** Records both inbound and outbound audio to WAV files for later analysis.

## Usage

1.  **Set up environment variables:** Create a `.env` file based on `.env.example` and fill in the necessary API keys and credentials.
2.  **Run the server:** Execute `python main.py` to start the server.
3.  **Make a call (optional):** To make a test call, run `python main.py --call=+1XXXXXXXXXX` (replace with a valid phone number).  The script will check if the number is allowed based on Twilio configuration.
4.  **Access the web interface (optional):**  The server provides a basic JSON endpoint at `/`.

## Installation

1.  Clone the repository: `git clone <repository_url>`
2.  Install dependencies: `pip install -r requirements.txt`

## Technologies Used

*   **Python:** The primary programming language for the backend.
*   **FastAPI:** A modern, fast (high-performance), web framework for building APIs.
*   **WebSockets:** Enables real-time bidirectional communication between the client (Twilio) and the server.
*   **Twilio:** A cloud communications platform used for handling voice calls.
*   **OpenAI:**  Provides the large language model and real-time transcription capabilities.  Specifically, utilizes GPT-4 and the `gpt-4o-realtime-preview` model.
*   **PyDub:** Used for audio manipulation and overlaying audio files.
*   **uvicorn:** An ASGI server implementation used to run the FastAPI application.
*   **python-dotenv:** Loads environment variables from a `.env` file.
*   **requests:** Used for making HTTP requests (although usage in this specific code is minimal).
*   **websockets:** A library providing WebSocket client functionality.
*   **audioop:** A Python module for basic audio operations.
*   **wave:**  A Python module for working with WAV audio files.

## Configuration

The application is configured using environment variables in a `.env` file:

*   `OPENAI_API_KEY`: Your OpenAI API key.
*   `TWILIO_ACCOUNT_SID`: Your Twilio Account SID.
*   `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token.
*   `PHONE_NUMBER_FROM`: Your Twilio phone number.
*   `DOMAIN`: The domain name or IP address of the server (defaults to `localhost`).
*   `PORT`: The port the server listens on (defaults to 5050).

## API Documentation

The application has a single endpoint:

*   `/`: Returns a JSON message indicating that the server is running.  Example: `{"message": "twilio media stream server is running!"}`.

The main functionality is provided through the `/media-stream` WebSocket endpoint.  This is not a standard REST API; it handles the real-time bidirectional communication with Twilio.

## Dependencies

See `requirements.txt` for a complete list of project dependencies.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Testing

Basic testing is implemented in `tests/test.py`. This script demonstrates how to overlay the inbound and outbound WAV files after a call.  More comprehensive testing is needed.
