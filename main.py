from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import databases

# === Настройки ===
SQLALCHEMY_DATABASE_URL = "sqlite:///./database.db"
database = databases.Database(SQLALCHEMY_DATABASE_URL)
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# === Модель Pydantic (для валидации) ===
class MenuItem(BaseModel):
    id: int
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

# Создаем таблицы
Base.metadata.create_all(bind=engine)
# === СТАРТОВЫЕ ДАННЫЕ ===
db = SessionLocal()                          # открываем сессию
if not db.query(DBMenuItem).first():         # если БД пустая
    starters = [
        DBMenuItem(id=1, name="Стейк рибай", description="Сочное ребро фирменной говядины. Цена за 100 г.", price=500.0),
        DBMenuItem(id=2, name="Плов", description="Узбекский плов с бараниной", price=800.0),
        DBMenuItem(id=3, name="Салат Цезарь", description="С курицей и пармезаном", price=600.0),
    ]
    db.add_all(starters)                     # добавляем 3 блюда
    db.commit()                              # сохраняем
db.close()                                   # закрываем сессию
# =========================

# === JWT АУТЕНТИФИКАЦИЯ ===
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

# Настройки
SECRET_KEY = "tvoi-super-secret-key-12345"  # Замени на случайную строку
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Фейковые пользователи
fake_users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("password123"),
    }
}

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

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

# === ЭНДПОИНТЫ ===
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = fake_users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    token = create_access_token(data={"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}

# Защищённый роут
@app.get("/menu/protected")
async def protected_menu(user: str = Depends(get_current_user)):
    return {"message": f"Привет, {user}! Это защищённое меню."}


# === FastAPI ===
app = FastAPI(
    title="Меню ресторана API",
    description="Полноценный CRUD API на FastAPI + SQLite",
    version="1.0.0"
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# === CRUD Эндпоинты ===

@app.get("/menu", response_model=list[MenuItem])
async def get_menu(user: str = Depends(get_current_user), db=Depends(get_db)):
    return db.query(DBMenuItem).all()

@app.post("/menu", response_model=MenuItem)
async def Добавить_позицию(item: MenuItem, db=Depends(get_db)):
    db_item = DBMenuItem(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.put("/menu/{item_id}", response_model=MenuItem)
async def обновить_позицию(item_id: int, item: MenuItem, db=Depends(get_db)):
    db_item = db.query(DBMenuItem).filter(DBMenuItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    for key, value in item.dict().items():
        setattr(db_item, key, value)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.delete("/menu/{item_id}")
async def Удалить_позицию(item_id: int, db=Depends(get_db)):
    db_item = db.query(DBMenuItem).filter(DBMenuItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(db_item)
    db.commit()
    return {"detail": "Item deleted successfully"}

# === Добавим стартовые данные (один раз) ===
@app.on_event("startup")
async def startup():
    db = SessionLocal()
    if db.query(DBMenuItem).count() == 0:
        items = [
            DBMenuItem(id=1, name="Стейк рибай", description="Сочное ребро, 100 гр.", price=500.0),
            DBMenuItem(id=2, name="Плов", description="Узбекский с бараниной", price=800.0),
            DBMenuItem(id=3, name="Салат Цезарь", description="С курицей и пармезаном", price=600.0),
        ]
        db.add_all(items)
        db.commit()
    db.close()
