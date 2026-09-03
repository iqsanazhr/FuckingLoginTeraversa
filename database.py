from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config import DATABASE_URL
from security import encrypt_secret, decrypt_secret, encrypt_with_pin, decrypt_with_pin

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True)
    email = Column(String(255), nullable=False)
    encrypted_password = Column(Text, nullable=False)
    password_salt = Column(String(50), nullable=True)  # Salt unik 128-bit untuk derivasi PIN
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    courses = relationship("CourseCache", back_populates="user", cascade="all, delete-orphan")

    def get_password(self, pin: str = None) -> str:
        """
        Buka password akun Unsoed.
        Jika akun menggunakan Zero-Knowledge E2EE, wajib menyertakan PIN 4-digit.
        """
        if self.password_salt:
            if not pin:
                raise ValueError("PIN 4-digit diperlukan untuk membuka password!")
            return decrypt_with_pin(self.encrypted_password, self.password_salt, pin)
        # Fallback master key jika akun lama belum memakai PIN
        return decrypt_secret(self.encrypted_password)

    def set_password(self, plain_password: str, pin: str = None):
        if pin:
            enc, salt = encrypt_with_pin(plain_password, pin)
            self.encrypted_password = enc
            self.password_salt = salt
        else:
            self.encrypted_password = encrypt_secret(plain_password)
            self.password_salt = None


class CourseCache(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    idjadwal = Column(String(50), nullable=False)
    course_name = Column(String(255), nullable=False)
    schedule_info = Column(String(255), nullable=True)
    alias = Column(String(50), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="courses")


class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False)
    idjadwal = Column(String(50), nullable=False)
    course_name = Column(String(255), nullable=False)
    token = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)  # BERHASIL / GAGAL
    response_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Engine & Session
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
    # Migrasi otomatis kolom password_salt jika belum ada
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_salt VARCHAR(50);"))
            conn.commit()
        except Exception:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN password_salt VARCHAR(50);"))
                conn.commit()
            except Exception:
                pass
    print("[*] Database tables initialized successfully.")


def get_user(telegram_id: int):
    with SessionLocal() as db:
        return db.query(User).filter(User.telegram_id == telegram_id).first()


def save_user(telegram_id: int, email: str, password_plain: str, pin: str = None, full_name: str = None) -> User:
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if pin:
            enc_pwd, salt = encrypt_with_pin(password_plain, pin)
        else:
            enc_pwd = encrypt_secret(password_plain)
            salt = None

        if not user:
            user = User(
                telegram_id=telegram_id,
                email=email,
                encrypted_password=enc_pwd,
                password_salt=salt,
                full_name=full_name,
            )
            db.add(user)
        else:
            user.email = email
            user.encrypted_password = enc_pwd
            user.password_salt = salt
            if full_name:
                user.full_name = full_name
            user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user


def delete_user(telegram_id: int) -> bool:
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            db.delete(user)
            db.commit()
            return True
        return False


def save_courses(telegram_id: int, courses_data: list):
    """
    courses_data: list of dict {'idjadwal': str, 'name': str, 'schedule': str, 'alias': str}
    """
    with SessionLocal() as db:
        # Hapus cache lama user ini
        db.query(CourseCache).filter(CourseCache.telegram_id == telegram_id).delete()

        for c in courses_data:
            course = CourseCache(
                telegram_id=telegram_id,
                idjadwal=c["idjadwal"],
                course_name=c["name"],
                schedule_info=c.get("schedule", ""),
                alias=c.get("alias", ""),
            )
            db.add(course)
        db.commit()


def get_courses(telegram_id: int) -> list:
    with SessionLocal() as db:
        return db.query(CourseCache).filter(CourseCache.telegram_id == telegram_id).all()


def find_course(telegram_id: int, query: str):
    """
    Mencari matkul berdasarkan query (bisa berupa idjadwal, alias, atau kemiripan nama)
    """
    query = query.strip().lower()
    with SessionLocal() as db:
        courses = db.query(CourseCache).filter(CourseCache.telegram_id == telegram_id).all()
        
        # 1. Cek exact match idjadwal
        for c in courses:
            if c.idjadwal == query:
                return c
                
        # 2. Cek exact match alias (misal: "upl", "erp", "kp")
        for c in courses:
            if c.alias and c.alias.lower() == query:
                return c

        # 3. Cek prefix / in name
        for c in courses:
            name_lower = c.course_name.lower()
            if query in name_lower or name_lower.startswith(query):
                return c

        # 4. Cek inisial / akronim nama matkul (e.g. Uji Kualitas Perangkat Lunak -> UKPL / UPL)
        for c in courses:
            words = [w for w in c.course_name.split() if w.isalpha()]
            initials = "".join([w[0].lower() for w in words])
            if query == initials:
                return c

        return None


def log_attendance(telegram_id: int, idjadwal: str, course_name: str, token: str, status: str, message: str):
    with SessionLocal() as db:
        log = AttendanceLog(
            telegram_id=telegram_id,
            idjadwal=idjadwal,
            course_name=course_name,
            token=token,
            status=status,
            response_message=message,
        )
        db.add(log)
        db.commit()
