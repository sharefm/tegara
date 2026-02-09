from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    mobile_number = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    verified = Column(Integer, default=0)  # 0 = not verified, 1 = SMS verified
    password_reset_count = Column(Integer, default=0)  # Track password reset attempts
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to domains
    domains = relationship("Domain", back_populates="user", cascade="all, delete-orphan")

class Domain(Base):
    __tablename__ = "domains"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    domain_name = Column(String, unique=True, nullable=False, index=True)
    domain_type = Column(String, nullable=False)  # 'custom' or 'temp'
    social_media_url = Column(String, nullable=False)  # URL to redirect to
    store_name = Column(String, nullable=True)  # Store/business name (for custom domains)
    is_active = Column(Integer, default=1)  # 1 = active, 0 = inactive
    subscription_status = Column(String, default='trial')  # 'trial', 'active', 'expired'
    created_at = Column(DateTime, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)  # Domain expiry date
    
    # Relationship to user
    user = relationship("User", back_populates="domains")

class OTPSession(Base):
    __tablename__ = "otp_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    mobile_number = Column(String, nullable=False, index=True)
    otp_code = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified = Column(Integer, default=0)  # 0 = not verified, 1 = verified
