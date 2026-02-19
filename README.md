# Intelligent AI-Based Mock Interview Feedback System

A web-based application that helps users practice mock interviews and receive intelligent, AI-driven feedback.
The system simulates interview scenarios, analyzes user responses, and provides insights to improve communication and interview performance.

---

## Features

* Mock interview simulation using AI
* Intelligent question generation
* Automated feedback and suggestions
* Web-based interactive interface
* Secure API key handling using environment variables
* Real-time analysis and response evaluation

---

## Installation

### Prerequisites

* Python 3.9 or higher
* Windows / Linux / macOS
* Internet connection (for AI APIs)

---

### Setup

1. Clone or download the repository

2. Navigate to the project directory

3. Create a virtual environment:

```bash
python -m venv venv
```

Activate the environment:

**Windows**

```bash
venv\Scripts\activate
```

**Linux / macOS**

```bash
source venv/bin/activate
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

### Start the Application

```bash
python app.py
```

The application will be available at:

```
http://127.0.0.1:5000
```

---

### Configure API Keys

Create a `.env` file in the project root and add:

```env
HUGGINGFACE_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
```

**Important:**

* Never upload `.env` to GitHub
* `.env` is already ignored using `.gitignore`

---

## Project Structure

```
Intelligent-AI-Based-Mock-Interview-Feedback-System/
│
├── app.py                # Main Flask application
├── deepseek.py           # AI logic and model interaction
├── keys.json             # API key placeholders (no secrets)
├── datasets/             # Supporting datasets
├── templates/            # HTML templates
│   ├── index.html
│   ├── result.html
│   └── feedback.html
├── static/               # CSS, JS, assets
├── .gitignore            # Git ignore rules
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation
```

---

## Core Modules

### `app.py`

* Flask web application entry point
* Handles routing, form input, and response rendering

### `deepseek.py`

* Contains AI interaction logic
* Sends prompts to AI models
* Processes responses for feedback

### `keys.json`

* Holds API key placeholders only
* Real keys are loaded from environment variables

---

## Technologies Used

* **Backend:** Flask
* **Programming Language:** Python
* **AI / NLP APIs:** Hugging Face, Gemini, DeepSeek, Groq, OpenRouter
* **Frontend:** HTML, CSS, JavaScript
* **Environment Management:** python-dotenv

---

## Security Notes

* API keys are stored securely using environment variables
* `.env` file is excluded from GitHub
* No sensitive information is committed to the repository

---

## Use Cases

* Students preparing for placements
* Job seekers practicing interviews
* Colleges for training and demonstrations
* AI-based interview skill assessment

---

## Conclusion

The Intelligent AI-Based Mock Interview Feedback System provides a practical and interactive platform for interview preparation.
By using AI-driven analysis and feedback, the system helps users build confidence and improve their interview skills effectively.

---



