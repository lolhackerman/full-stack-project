# Full‑Stack Take‑Home: “Tool-Enabled Chatbot”

**Goal**
As a full stack developer, you will be tested by building an end-to-end chatbot that can call *at least one* tool. The bot should use an OpenAI model (or any model of your choice) and invoke your chosen tool when appropriate. This tool can be anything—from a weather lookup to a simple calculator or any other capability you would like to showcase. We will provide you with an OpenAI API key via email with a small budget.

If you have any questions before starting or during the exercise, please send them to us. We will get back to you with the answers as soon as possible.

As an AI first company, we don't mind but in fact encourage you to use all available tools and resources at your disposal (codex, Github CoPilot, StackOverflow, etc.).

> **Timebox:** Aim for ~6–8 hours of focused effort. It’s OK if you don’t complete all stretch goals. Optimize for clarity, quality, and trade‑offs. We are a team that values communication as well as working fast. We ask for you to take at most 5 days to complete the project. If you need additional time, please let us know.
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

    * Working backend with good routing naming conventions that work with the UI.

3. **LLM Tool Integration**

    * Implement at least one tool the model can call via your backend (e.g., calculator, weather lookup, todo list manager, etc.).
    * The bot should decide **when** to call the tool based on the conversation.
    * Document what the tool does and any external services or data sources it uses.

4. **Chat Memory**

    * The chatbot is aware of previous messages and can remember them.
      * Does not need to be persistent if user refreshes the page.

5. **Ability to delete messages**

    * User should be able to delete messages from the chat history.


6. **Working end‑to‑end flow**

    * Example: user asks a question → model triggers your tool → server runs the tool → bot replies with a concise, helpful answer.
    * Basic error handling (invalid inputs, network failure, etc.) with useful messaging.

7. **README**

    * Setup & run instructions, environment variables, and short architecture notes (what you built, trade‑offs, what you would do next).

---

## Above‑and‑Beyond (Stretch)

1. **User Feedback**: User can thumb up/down a message.
2. **Plan‑and‑Execute Agent**

    * Implement a light planning layer: the model produces an explicit **plan** then runs through each step.

3. **Streamed Responses**

    * **SSE/WebSocket** streaming of assistants **thinking** or **plan steps**.

4. **Persistence**

    * Store conversations in a database **SQL/MongoDB/ect**.

5. **Deployment**

    * Deploy to a cloud of your choice (e.g., Vercel/Firebase/Heroku/Supabase/ect).
    * Provide a public URL in the README.

* These are all optional, but we encourage you to try them out. If you have other features that you think would be cool, feel free to add them and document it in the README.

---

## Data Sources

Feel free to choose any APIs or data sources that suit the tool you want to build. Document how to obtain access and any setup required so we can run it locally.

---

## What we are looking for

When assessing the results, these are the main areas we will be looking at.

It does not need to be perfect. We will be assessing it holistically.

These are the areas we are generally interested in:

- The feature is complete and works according to minimum requirements. It is stable, and edge cases are handled in a sensible, thought-out manner. There is error handling and authentication is considered (Does not need to be implemented).
- The code is well organized, easy to understand and readable, it follows best practices.
- Feature implemented in a user-friendly, UI looks cohesive and delightful.
- Well structured README with clear instructions on how to run the project and an overview on how you built it.
- Mostly importantly, we want to see your communication style throughout the project. As a small team that moves fast, **communication is extremely important** to us.
---

## Submission
When done, please email us:
* Public GitHub repo link.
* In your repo, please update the **README** with:
    * clear local run instructions for **both** the UI and your chosen API (`py-api` or `ts-api`) including env vars and how to obtain API keys if needed.
    * brief architecture notes & trade‑offs.
    * any stretch goals you implemented.
* deployment URL if you did deploy.

---

 ## After Submission 
We will do an internal code review of your code and share feedback with you over email. If we like what we see, we will invite you to the technical interview with the team to discuss your solution.
