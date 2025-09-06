from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os, json

app = Flask(__name__)

# ---------- Config ----------
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")
# Prefer DATABASE_URL if you later add Postgres on Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL",
    'sqlite:///database.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- Telegram (env vars recommended) ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{"8056386126:AAHyreWcjf0cGLN-aCB98V3wV2stuKcr5d4"}/sendMessage"
        data = {"chat_id": "1219867679", "text": message}
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        print("Telegram notification failed:", e)

# ---------- Models ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(100), nullable=False)
    members_needed = db.Column(db.Integer, default=7)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default="open")

# ---------- Routes ----------
@app.route('/')
def home():
    # If you want the homepage public, comment the next 3 lines.
    if "user_id" not in session:
        return redirect(url_for("login"))

    events = Event.query.all()

    # Load buffet data safely (won’t crash if file missing)
    buffet = {"title": "What's Included in the 7@777 Buffet",
              "note": "Items vary by day & location; buffet is unlimited when 7 dine together via Groupies.",
              "categories": []}
    try:
        menu_path = os.path.join(app.root_path, 'static', 'menu_777.json')
        with open(menu_path, 'r', encoding='utf-8') as f:
            buffet = json.load(f)
    except FileNotFoundError:
        pass

    return render_template("events.html", events=events, buffet=buffet)

@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form['username'].strip()
        raw_password = request.form['password']
        if not username or not raw_password:
            flash("Username and password are required.", "error")
            return redirect(url_for("signup"))

        if User.query.filter_by(username=username).first():
            flash("User already exists!", "error")
            return redirect(url_for("signup"))

        password_hash = generate_password_hash(raw_password)
        new_user = User(username=username, password=password_hash)
        db.session.add(new_user)
        db.session.commit()

        send_telegram(f"🎉 New signup: {username}")
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username'].strip()
        entered_password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, entered_password):
            session['user_id'] = user.id
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    group_members = Group.query.filter_by(event_id=event_id, status="open").all()
    return render_template("event_detail.html", event=event, members=len(group_members))

@app.route('/join/<int:event_id>')
def join_event(event_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    event = Event.query.get_or_404(event_id)

    # If user already joined any open/closed record for this event, don’t duplicate
    if Group.query.filter_by(event_id=event_id, user_id=user_id).first():
        return redirect(url_for("event_detail", event_id=event_id))

    # Count current open members AFTER checking duplication
    group_members = Group.query.filter_by(event_id=event_id, status="open").all()

    if len(group_members) < event.members_needed:
        new_member = Group(event_id=event_id, user_id=user_id)
        db.session.add(new_member)
        db.session.commit()
        group_members.append(new_member)  # reflect the new count in memory

    if len(group_members) >= event.members_needed:
        for member in group_members:
            member.status = "closed"
        db.session.commit()
        send_telegram(f"✅ Group for {event.event_name} is now FULL ({event.members_needed} members)")
        flash("Group is full! See your Telegram (if connected) for updates.", "success")

    return redirect(url_for('event_detail', event_id=event_id))

@app.route('/logout')
def logout():
    session.pop("user_id", None)
    flash("Logged out.", "success")
    return redirect(url_for("login"))

# ---------- Health (optional) ----------
@app.route('/healthz')
def healthz():
    return "ok", 200

# ---------- Run ----------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not Event.query.first():
            bbq = Event(event_name="BBQ Nation 7@777 (Group of 7)", members_needed=7)
            db.session.add(bbq)
            db.session.commit()
    app.run(debug=True)
