# 🎨 ComicCraft – AI Comic Story Creator Using Gemini Models

ComicCraft is an AI-powered web application that generates structured comic stories from simple user ideas using the **Google Gemini API**.

## 🚀 Features

* 🤖 AI-powered comic story generation
* 👤 Automatic character and setting creation
* 📖 3-chapter story with actions and dialogue
* 💾 Save and manage comics
* 📋 Copy generated stories
* 📄 Download as TXT
* 📕 Download as PDF
* 📚 Comic history

## 🛠️ Technologies

* Python
* FastAPI
* HTML, CSS & JavaScript
* Google Gemini API
* Jinja2
* Uvicorn
* ReportLab
* JSON

## ⚙️ How It Works

```text
User Idea
   ↓
Frontend
   ↓
FastAPI Backend
   ↓
Google Gemini API
   ↓
Generated Comic Story
   ↓
Display / Save / Download
```

## ▶️ Run the Project

Install the required packages:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

Start the server:

```bash
uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

⚠️ **Never upload your `.env` file or Gemini API key to GitHub.**

## 👥 Team

**Government Arts and Science College, Thondamuthur**
**Department of Computer Science**
**Academic Year: 2026–2027**

* Kritesh R P
* Ranjith E
* Muthu C

## 📌 Project Status

Academic mini-project demonstrating the integration of **Generative AI with a web application**.
