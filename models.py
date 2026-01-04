from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Store(Base):
    __tablename__ = "stores"
    
    id = Column(Integer, primary_key=True, index=True)
    store_name = Column(String, unique=True, index=True, nullable=False)
    owner_name = Column(String, nullable=False)
    mobile_number = Column(String, unique=True, index=True, nullable=False)
    facebook_page = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class OTPSession(Base):
    __tablename__ = "otp_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    mobile_number = Column(String, nullable=False)
    store_name = Column(String, nullable=False)
    otp_code = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified = Column(Integer, default=0)  # 0 = not verified, 1 = verified
