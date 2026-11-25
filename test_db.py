
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

with app.app_context():
    try:
        result = db.session.execute(
            text("SELECT DATABASE()")
        )

        print("Connected to:", result.scalar())

        tables = db.session.execute(
            text("SHOW TABLES")
        )

        for table in tables:
            print(table[0])

        print("MySQL connection successful!")

    except Exception as e:
        print("Database connection failed:", e)
