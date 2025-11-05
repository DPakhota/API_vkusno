# main.py — полностью рабочий код для Render
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import List
import uvicorn

# === 1. Настройки БД ===
SQLALCHEMY_DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# === 2. Pydantic модель (для валидации) ===
class MenuItem(BaseModel):
    id: int | None = None  # id — опционально, БД генерирует
    name: str
    description: str
    price: float

    class Config:
        from_attributes = True  # для возврата из SQLAlchemy

# === 3. Модель БД ===
class DBMenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    price = Column(Float)

# Создаём таблицы
Base.metadata.create_all(bind=engine)

# === 4. FastAPI приложение ===
app = FastAPI(
    title="Меню ресторана API",
    description="CRUD API с JWT-авторизацией и SQLite",
    version="1.0.0"
)

# === 5. JWT Аутентификация ===
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

SECRET_KEY = "tvoi-super-secret-key-12345-change-in-prod"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["argon2", "pbkdf2_sha256"], deprecated="auto")

# Фейковые пользователи
fake_users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("password123"),
    }
}

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username not in fake_users_db:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# === 6. Dependency для БД ===
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# === 7. Эндпоинты ===

@app.get("/")
async def root():
    return {"message": "API Vkusno работает! Swagger: /docs"}

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

# === CRUD с защитой ===
@app.get("/menu", response_model=List[MenuItem])
async def get_menu(user: str = Depends(get_current_user), db=Depends(get_db)):
    return db.query(DBMenuItem).all()

@app.post("/menu", response_model=MenuItem)
async def create_item(item: MenuItem, user: str = Depends(get_current_user), db=Depends(get_db)):
    db_item = DBMenuItem(**item.dict(exclude_unset=True))
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return MenuItem.from_orm(db_item)

@app.put("/menu/{item_id}", response_model=MenuItem)
async def update_item(
    item_id: int,
    item: MenuItem,
    user: str = Depends(get_current_user),
    db=Depends(get_db)
):
    db_item = db.query(DBMenuItem).filter(DBMenuItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    for key, value in item.dict(exclude_unset=True).items():
        setattr(db_item, key, value)
    db.commit()
    db.refresh(db_item)
    return MenuItem.from_orm(db_item)

@app.delete("/menu/{item_id}")
async def delete_item(item_id: int, user: str = Depends(get_current_user), db=Depends(get_db)):
    db_item = db.query(DBMenuItem).filter(DBMenuItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(db_item)
    db.commit()
    return {"detail": "Item deleted"}

# === 8. Стартовые данные ===
@app.on_event("startup")
async def startup_event():
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

# === 9. Запуск (для локального теста) ===
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)