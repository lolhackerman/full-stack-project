from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def index():
    """Basic health check endpoint."""
    return jsonify(message="Hello from ThreadWise Flask API"), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
