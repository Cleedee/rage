
from flask import Blueprint, flash, redirect, render_template, url_for

raiz = Blueprint(
    "home", 
    __name__, 
    template_folder="templates",
    static_folder="static",
    url_prefix="/")

@raiz.get('/')
def index():
    return render_template('home/index.html')

