# Outbound AI Calling Agent

This project is a full-stack application designed to automate outbound calling campaigns. It integrates with Twilio for telephony, ElevenLabs for realistic text-to-speech, and OpenAI for conversational AI. The system manages leads from Google Sheets, tracks call history, and provides a dashboard to monitor campaign performance.

## Features

- **Automated Outbound Calling**: A scheduler initiates calls to a list of leads.
- **Conversational AI**: Uses OpenAI (GPT models) to have natural conversations with leads.
- **Realistic Voice**: Integrates with ElevenLabs for high-quality, human-sounding text-to-speech in multiple languages (English and Telugu).
- **Lead Management**: Syncs leads from a Google Sheet and stores them in MongoDB.
- **Call Dashboard**: A React-based frontend to monitor call history, lead status, and system configuration.
- **WhatsApp Follow-up**: Automatically sends a follow-up message via WhatsApp if a lead shows interest.
- **Cloud-Ready**: Pre-configured for deployment on Railway (backend) and Vercel (frontend).

## Tech Stack

- **Backend**: Python, FastAPI, MongoDB (Motor), Twilio, ElevenLabs, OpenAI
- **Frontend**: React.js, CSS
- **Database**: MongoDB Atlas
- **Deployment**: Railway (Backend), Vercel (Frontend)

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js and Yarn
- A MongoDB Atlas account
- A Twilio account with a configured phone number
- An ElevenLabs account
- An OpenAI API key

### 1. Clone the Repository

```bash
git clone https://github.com/Vinay4562/Calling-AI-Agent.git
cd Calling-AI-Agent
```

### 2. Backend Setup

The backend is a Python FastAPI application located in the `backend/` directory.

**a. Create a Virtual Environment**

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
```

**b. Install Dependencies**

```bash
pip install -r backend/requirements.txt
```

**c. Configure Environment Variables**

Create a `.env` file inside the `backend/` directory by copying the example file:

```bash
cp backend/.env.example backend/.env
```

Now, fill in the values in `backend/.env` with your credentials:

- `MONGO_URL`: Your MongoDB Atlas connection string.
- `DB_NAME`: The name of your database (e.g., `calling_agent_db`).
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`: Your Twilio credentials.
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`: Your ElevenLabs credentials.
- `LLM_API_KEY`: Your OpenAI API key.
- `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`: Your Google Sheets credentials.
- `WEBHOOK_BASE_URL`: For local development, use a tunneling service like Ngrok. For production, this will be your Railway URL.

**d. Run the Backend Server**

```bash
cd backend
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at `http://localhost:8000`.

### 3. Frontend Setup

The frontend is a React application located in the `frontend/` directory.

**a. Install Dependencies**

```bash
cd frontend
yarn install
```

**b. Configure Environment Variables**

Create a `.env` file in the `frontend/` directory:

```bash
cp .env.example .env
```

Update `frontend/.env` to point to your backend API:

```
REACT_APP_BACKEND_URL=http://localhost:8000
```

**c. Run the Frontend Server**

```bash
yarn start
```

The frontend will be available at `http://localhost:3000`.

## Deployment

### Backend (Railway)

1.  **Push to GitHub**: Ensure your latest code is on GitHub.
2.  **Create a New Project**: In Railway, create a new project and select your GitHub repository.
3.  **Configure Settings**:
    -   **Root Directory**: Set to `backend`.
    -   Railway will automatically use the `Procfile` to determine the start command (`uvicorn`).
4.  **Add Environment Variables**: In the project variables, add all the key-value pairs from your local `backend/.env` file.
5.  **Update Webhook URL**: Once deployed, Railway will provide a public URL. Update the `WEBHOOK_BASE_URL` variable in Railway with this new URL.

### Frontend (Vercel)

1.  **Push to GitHub**: Ensure your latest code is on GitHub.
2.  **Import Project**: In Vercel, import your GitHub repository.
3.  **Configure Project**:
    -   **Root Directory**: Set to `frontend`.
    -   Vercel will auto-detect that it is a Create React App project.
4.  **Add Environment Variables**:
    -   `REACT_APP_BACKEND_URL`: Set this to your public Railway backend URL.
5.  **Deploy**: Click "Deploy". Vercel will build and deploy the frontend.

### Final Step: Update CORS

For the deployed frontend to communicate with the backend, you must update the `CORS_ORIGINS` variable in your **Railway** project to include your Vercel URL.

Example:
`CORS_ORIGINS=https://your-frontend-url.vercel.app`
