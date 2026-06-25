from sqlalchemy import create_engine, Column, Integer, String, DateTime, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
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
    role = Column(String, default="Не указана")
    video_file_id = Column(String)  # ТОЛЬКО ID!
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.datetime.now)

Base.metadata.create_all(bind=engine)

@contextmanager
def get_session():
    """Автоматически открывает и закрывает сессию"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
