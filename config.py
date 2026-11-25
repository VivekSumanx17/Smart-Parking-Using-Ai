
import os
from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv()

class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]

    SQLALCHEMY_DATABASE_URI = URL.create(
        drivername="mysql+pymysql",
        username="parkvision_app",
        password=os.environ["DB_PASSWORD"],
        host="localhost",
        port=3306,
        database="parkvision"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv(
        "MAIL_USE_TLS", "True"
    ).lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")
