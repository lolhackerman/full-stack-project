# Full‑Stack Take‑Home: “Weather Chatbot”

**Goal**
As a full stack developer, you will be tested by building an end-to-end “weathercaster” bot. The bot uses an OpenAI model (or any model of your choice) and calls a weather API when appropriate to answer questions like “What is the weather in Boulder CO today?”. We will provide you with an openai api key via email with a small budget. 

If you have any questions before starting or during the exercise, please send them to us. We will get back to you with the answers as soon as possible.

As an AI first company, we don't mind but in fact encourage you to use all available tools and resources at your disposal.

> **Timebox:** Aim for ~6–8 hours of focused effort. It’s OK if you don’t complete all stretch goals. Optimize for clarity, quality, and trade‑offs. We are a team that values communication as well as working fast. We ask for you to take at most a week to complete the project. If you need additional time, please let us know.
> 
> **Stack:** Frontend in **React + TailwindCSS**. Backend in **Node (TypeScript/JS)** *or* **Python**. Any build tooling is fine.

---

## Starter repository

* We will provide a repo with three folders:

    * `ui/` – bare‑bones React + Tailwind starter
    * `py-api/` – bare‑bones Flask starter
    * `ts-api/` – bare‑bones TypeScript Express starter
* You may **fork this repo** *or* start from scratch.
* Use any build tooling you prefer.

---

## Minimum Requirements (MVP)

1. **Chat UI (React + Tailwind)**

    * Text input and send button.
    * Message list with clear separation of **user** and **bot** messages.
    * Loading/disabled states and basic error UI.

2. **Backend API** (Node or Python)

    * Single `/api/chat` endpoint that accepts a conversation history and latest user message.
    * Server calls OpenAI’s chat API and implements **tool/function calling** for weather lookup.

3. **Weather lookup tool**

    * Accepts **location string or ZIP/postal code** and fetches forecast from a weather API.
    * The bot should decide **when** to call the weather tool.

4. **Chat Memory**

    * The chatbot is aware of previous messages and can remember them.

5. **Working end‑to‑end flow**

    * User asks a weather question → model triggers the tool → server fetches weather → bot replies with a concise, friendly forecast.
    * Basic error handling (invalid location, network failure) with a useful message to the user.

6. **README**

    * Setup & run instructions, environment variables, and short architecture notes (what you built, trade‑offs, what you would do next).

---

## Above‑and‑Beyond (Stretch)

1. **Plan‑and‑Execute Agent**

    * Implement a light planning layer: the model produces an explicit **plan** then runs through each step.

2. **Streamed Responses**

    * **SSE/WebSocket** streaming of assistants **thinking** or **plan steps**.

3. **Persistence**

    * Store conversations in a database **SQL/MongoDB/ect**.

4. **Ability to delete messages**

    * User should be able to delete messages from the chat history.

5. **Deployment**

    * Deploy to a cloud of your choice (e.g., Vercel/Firebase/Heroku/Supabase/ect).
    * Provide a public URL in the README.

* These are all optional, but we encourage you to try them out. If you have other features that you think would be cool, feel free to add them and document it in the README.

---

## Data Sources

* **Weather API:** [WeatherStack](https://weatherstack.com/): They have a free tier.
  * Documentation:  https://weatherstack.com/documentation

---

## What we are looking for

When assessing the results, these are the main areas we will be looking at.

It does not need to be perfect. We will be assessing it holistically.

These are the areas we are generally interested in:

- The feature is complete and works according to requirements. It is stable, and edge cases are handled in a sensible, thought-out manner. There is error handling and authentication is considered.
- The code is well organized, easy to understand and readable, it follows best practices.
- Feature implemented in a user-friendly, UI looks cohesive and delightful.
- Well structured README with clear instructions on how to run the project and an overview on how you built it.
- Mostly importantly, we want to see your communication style throughout the project. As a small team that moves fast, **communication is extremely important** to us.
---

## Submission

* Public GitHub repo link.
* **README** with:
    * clear local run instructions for **both** the UI and your chosen API (`py-api` or `ts-api`) including env vars and how to obtain API keys if needed.
    * brief architecture notes & trade‑offs.
    * deployment URL if you attempted the stretch deploy.
* The app is **fully functional** and meets all **Minimum Requirements**.
* After it’s done, we will do an internal code review of your code and share feedback with you over email. If we like what we see, we will invite you to the technical interview with the team to discuss your solution.
---
