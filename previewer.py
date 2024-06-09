import flask

app = flask.Flask(__name__)


@app.route("/")
def index():
    return flask.render_template("index.html")


@app.route("/bc")
def bc():
    return flask.render_template("bc.html")


@app.route("/network_layout")
def network():
    with open("network_layout.json") as f:
        return flask.jsonify(flask.json.load(f))


@app.route("/state")
def state():
    with open("state.json") as f:
        return flask.jsonify(flask.json.load(f))


app.run(port=8080, debug=True)
