from flask import Flask, jsonify, render_template
from script import fetch_trending_topics, save_to_mongo, process_trending_data

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return render_template('index.html') 

@app.route("/trending", methods=["GET"])
def fetch_trends():
    trending_topics, ip_address = fetch_trending_topics()
    structured_data = process_trending_data([{"trending_topics": trending_topics}])
    save_to_mongo(trending_topics, ip_address)
    return jsonify({"status": "success", "trending_topics": structured_data["trending_topics"], "mongo_data": 'Saved to Mongo'})

if __name__ == "__main__":
    app.run(debug=True)
