from sqlalchemy import Column, Integer, String, Float, BigInteger, ForeignKey, Date, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime

class PostType(Base):
    __tablename__ = "post_type_table"

    post_type_id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, nullable=False)
    
    posts = relationship("Post", back_populates="post_type")

class Post(Base):
    __tablename__ = "post_table"

    post_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    content = Column(String, nullable=False)
    child_id = Column(BigInteger, nullable=True)
    user_id = Column(BigInteger, ForeignKey("user_table.user_id"), nullable=False)
    media_link = Column(String, nullable=True)
    creation_date = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    views_count = Column(BigInteger, nullable=False, default=0)
    post_type_id = Column(BigInteger, ForeignKey("post_type_table.post_type_id"), nullable=False)
    
    user = relationship("User", back_populates="posts")
    post_type = relationship("PostType", back_populates="posts")
    likes = relationship("Like", back_populates="post")
    tags = relationship("TagForPost", back_populates="post")

class TagType(Base):
    __tablename__ = "tag_type_table"

    tag_type_id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, nullable=False)
    
    tags = relationship("Tag", back_populates="tag_type")

class Tag(Base):
    __tablename__ = "tag_table"

    tag_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    tag_type_id = Column(BigInteger, ForeignKey("tag_type_table.tag_type_id"), nullable=False)
    
    tag_type = relationship("TagType", back_populates="tags")
    post_tags = relationship("TagForPost", back_populates="tag")
    user_tags = relationship("TagForUser", back_populates="tag")

class TagForPost(Base):
    __tablename__ = "tags_for_post_table"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    post_id = Column(BigInteger, ForeignKey("post_table.post_id"), nullable=False)
    tag_id = Column(BigInteger, ForeignKey("tag_table.tag_id"), nullable=False)
    
    post = relationship("Post", back_populates="tags")
    tag = relationship("Tag", back_populates="post_tags")

class TagForUser(Base):
    __tablename__ = "tags_for_user_table"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("user_table.user_id"), nullable=False)
    tag_id = Column(BigInteger, ForeignKey("tag_table.tag_id"), nullable=False)
    
    user = relationship("User", back_populates="tags")
    tag = relationship("Tag", back_populates="user_tags")

class Like(Base):
    __tablename__ = "like_table"

    like_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    post_id = Column(BigInteger, ForeignKey("post_table.post_id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("user_table.user_id"), nullable=False)
    
    post = relationship("Post", back_populates="likes")
    user = relationship("User", back_populates="likes")

class ProfileType(Base):
    __tablename__ = "profile_type_table"

    type_id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, nullable=False)
    
    users = relationship("User", back_populates="profile_type")

class User(Base):
    __tablename__ = "user_table"

    user_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    login = Column(String, nullable=False)
    password = Column(String, nullable=False)
    type_id = Column(BigInteger, ForeignKey("profile_type_table.type_id"), nullable=False)
    name = Column(String, nullable=False)
    image_link = Column(String, nullable=True)
    description = Column(String, nullable=True)
    rating = Column(Float, nullable=False, default=0.0)
    
    profile_type = relationship("ProfileType", back_populates="users")
    posts = relationship("Post", back_populates="user")
    likes = relationship("Like", back_populates="user")
    tags = relationship("TagForUser", back_populates="user")
    change_requests = relationship("ChangeRequest", back_populates="user")
    education_programs = relationship("EducationProgram", back_populates="user")

class EducationType(Base):
    __tablename__ = "education_type_table"

    education_type_id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, nullable=False)
    
    programs = relationship("EducationProgram", back_populates="education_type")

class EducationProgram(Base):
    __tablename__ = "education_program_table"

    program_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("user_table.user_id"), nullable=False)
    code = Column(BigInteger, nullable=False)
    name = Column(String, nullable=False)
    time = Column(BigInteger, nullable=False)
    education_type_id = Column(BigInteger, ForeignKey("education_type_table.education_type_id"), nullable=False)
    description = Column(String, nullable=False)
    quota = Column(BigInteger, nullable=False)
    
    user = relationship("User", back_populates="education_programs")
    education_type = relationship("EducationType", back_populates="programs")
    learning_plans = relationship("LearningPlan", back_populates="program")
    change_requests = relationship("ChangeRequest", back_populates="program")

class Subject(Base):
    __tablename__ = "subject_table"

    subject_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    
    learning_plans = relationship("LearningPlan", back_populates="subject")

class LearningPlan(Base):
    __tablename__ = "learning_plan_table"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    program_id = Column(BigInteger, ForeignKey("education_program_table.program_id"), nullable=False)
    subject_id = Column(BigInteger, ForeignKey("subject_table.subject_id"), nullable=False)
    hours = Column(BigInteger, nullable=False)
    semester = Column(BigInteger, nullable=False)
    
    program = relationship("EducationProgram", back_populates="learning_plans")
    subject = relationship("Subject", back_populates="learning_plans")

class ChangeRequest(Base):
    __tablename__ = "change_request_table"

    change_request_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    description = Column(String, nullable=False)
    from_id = Column(BigInteger, ForeignKey("user_table.user_id"), nullable=False)
    program_id = Column(BigInteger, ForeignKey("education_program_table.program_id"), nullable=False)
    
    user = relationship("User", back_populates="change_requests")
    program = relationship("EducationProgram", back_populates="change_requests")

class DocumentEvaluation(Base):
    __tablename__ = "document_evaluation_table"
    
    eval_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("user_table.user_id"), nullable=False)
    document_type = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    recipient = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    issuer = Column(String, nullable=True)
    document_date = Column(String, nullable=True)
    details = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    evaluation_date = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    
    user = relationship("User", backref="document_evaluations") 