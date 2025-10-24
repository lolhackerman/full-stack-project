"""Development entrypoint delegating to the application package."""

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.main import app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
