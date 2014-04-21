import os
import json
from flask import Flask, request, Response
from flask import render_template, send_from_directory, url_for

app = Flask(__name__)

app.config.from_object('quikmart.settings')

import quikmart.core
import quikmart.models
import quikmart.controllers

