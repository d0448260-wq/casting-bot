#database.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()
engine = create_engine('sqlite:///casting.db', connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(bind=engine)

class Application(Base):
    __tablename__ = 'applications'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    username = Column(String)
    name = Column(String)
    age = Column(Integer)
    city = Column(String)
    video_file_id = Column(String)  # Telegram file_id видео
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.datetime.now)
    channel_message_id = Column(Integer, nullable=True)

class Vote(Base):
    __tablename__ = 'votes'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    application_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.now)

Base.metadata.create_all(bind=engine)