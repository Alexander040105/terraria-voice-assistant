from flask import Flask, render_template
import os
app = Flask(__name__)

@app.route("/")
def home():
    return render_template(os.path("v2", "index.html"))