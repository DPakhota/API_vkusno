from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import databases

# === Настройки ===
SQLALCHEMY_DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# === Модели ===
class MenuItem(BaseModel):
    # УБРАЛИ id — БД генерирует сама!
    name: str
    description: str
    price: float

# === Модель БД ===
class DBMenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    price = Column(Float)

# Создаём таблицы
Base.metadata.create_all(bind=engine)

# === JWT АУТЕНТИФИКАЦИЯ (БЕЗ BCRYPT) ===
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

# Используем argon2 вместо bcrypt
pwd_context = CryptContext(schemes=["argon2", "pbkdf2_sha256"], deprecated="auto")

# Фейковые пользователи
fake_users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("password123"),
    }
}

# Остальное без изменений
def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, "tvoi-super-secret-key-12345", algorithm="HS256")

async def get_current_user(token: str = Depends(OAuth2PasswordBearer(tokenUrl="login"))):
    try:
        payload = jwt.decode(token, "tvoi-super-secret-key-12345", algorithms=["HS256"])
        username: str = payload.get("sub")
        if username not in fake_users_db:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# === Dependency ===
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# === ЭНДПОИНТЫ ===
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = fake_users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    token = create_access_token(data={"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/menu/protected")
async def protected_menu(user: str = Depends(get_current_user)):
    return {"message": f"Привет, {user}! Это защищённое меню."}

# === CRUD ===
@app.get("/menu", response_model=list[MenuItem])
async def get_menu(db=Depends(get_db)):
    return db.query(DBMenuItem).all()

@app.post("/menu", response_model=MenuItem)
async def create_item(item: MenuItem, db=Depends(get_db)):
    db_item = DBMenuItem(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    # Возвращаем с id
    return MenuItem(id=db_item.id, name=db_item.name, description=db_item.description, price=db_item.price)

@app.put("/menu/{item_id}", response_model=MenuItem)
async def update_item(item_id: int, item: MenuItem, db=Depends(get_db)):
    db_item = db.query(DBMenuItem).filter(DBMenuItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    for key, value in item.dict().items():
        setattr(db_item, key, value)
    db.commit()
    db.refresh(db_item)
    return MenuItem(id=db_item.id, **item.dict())

@app.delete("/menu/{item_id}")
async def delete_item(item_id: int, db=Depends(get_db)):
    db_item = db.query(DBMenuItem).filter(DBMenuItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(db_item)
    db.commit()
    return {"detail": "Item deleted"}

# === СТАРТОВЫЕ ДАННЫЕ (ОДИН РАЗ) ===
@app.on_event("startup")
async def startup():
    db = SessionLocal()
    if db.query(DBMenuItem).count() == 0:
        items = [
            DBMenuItem(name="Стейк рибай", description="Сочное ребро, 100 гр.", price=500.0),
            DBMenuItem(name="Плов", description="Узбекский с бараниной", price=800.0),
            DBMenuItem(name="Салат Цезарь", description="С курицей и пармезаном", price=600.0),
        ]
        db.add_all(items)
        db.commit()
    db.close()