# MongoDB Setup (Quick)

Follow these steps to persist chat history with MongoDB instead of the in-memory fallback.

1. Install MongoDB
   - Local (macOS): `brew tap mongodb/brew && brew install mongodb-community && brew services start mongodb-community`
   - Atlas (cloud): create a free cluster, add a database user, whitelist your IP, and copy the connection string.

2. Install API dependencies
   ```
   cd py-api
   pip install -r requirements.txt
   ```

3. Configure environment
   ```
   cp .env.example .env
   ```
   Edit `.env`:
   ```env
   ENABLE_MONGODB=true
   MONGODB_URI=mongodb://localhost:27017/
   # For Atlas, paste mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
   MONGODB_DATABASE=cover_letter_app
   OPENAI_API_KEY=your_actual_api_key_here
   ```

4. Run the API
   ```
   python app.py
   ```
   Startup loads `.env`, connects to MongoDB when enabled, and creates the needed indexes (includes a 90-day TTL).

Need to disable it later? Set `ENABLE_MONGODB=false` and restart the API to return to in-memory storage.
