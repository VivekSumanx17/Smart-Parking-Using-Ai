import os
from contextlib import contextmanager
from urllib.parse import urlsplit, unquote
import pymysql
from pymysql.cursors import DictCursor

def connection():
    url=os.environ.get('DATABASE_URL','')
    if not url.startswith('mysql+pymysql://'):
        raise RuntimeError('DATABASE_URL must begin with mysql+pymysql://')
    parsed=urlsplit(url.replace('mysql+pymysql://','mysql://',1))
    return pymysql.connect(host=parsed.hostname or 'localhost',port=parsed.port or 3306,user=unquote(parsed.username or ''),password=unquote(parsed.password or ''),database=parsed.path.lstrip('/'),charset='utf8mb4',cursorclass=DictCursor,autocommit=False)
