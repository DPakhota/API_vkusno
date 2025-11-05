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
class ToDoItem(BaseModel):
    id: int
    task: str
    description: str
    completed: bool

# === Модель БД ===
class DBToDoList(Base):
    __tablename__ = "ToDo_list"
    id = Column(Integer, primary_key=True, index=True)
    task = Column(String, index=True)
    description = Column(String)

# Создаем таблицы
Base.metadata.create_all(bind=engine)
# === СТАРТОВЫЕ ДАННЫЕ ===
db = SessionLocal()                          # открываем сессию
if not db.query(DBToDoList).first():         # если БД пустая
    starters = [
        DBToDoList(id=1, task="Отправить отчет Шефу", description="Х-отчет в конце дня. Не забыть!", completed=bool,)
        DBToDoList(id=2, task="Поставить сигнализацию в конце смены", description="Проверить горит-ли сигнал охраны", completed=bool),
        DBToDoList(id=3, task="Поставить буильник на час раньше", description="Утром нужно будет забрать дочку с рисования", completed=bool),
    ]
    db.add_all(starters)                     # добавляем 3 задачи
    db.commit()                              # сохраняем
db.close()                                   # закрываем сессию
# =========================

# === FastAPI ===
app = FastAPI(
    title="ToDo list API",
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

@app.get("/todo", response_model=list[ToDoList])
async def Список_задач(db=Depends(get_db)):
    return db.query(DBToDoList).all()

@app.post("/menu", response_model=ToDoList)
async def Добавить_задачу(item: ToDoList, db=Depends(get_db)):
    db_item = DBToDoList(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.put("/menu/{item_id}", response_model=ToDoList)
async def Редактировать_задачу(item_id: int, item: ToDoList, db=Depends(get_db)):
    db_item = db.query(DBToDoList).filter(DBToDoList.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    for key, value in item.dict().items():
        setattr(db_item, key, value)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.delete("/menu/{item_id}")
async def Удалить_задачу(item_id: int, db=Depends(get_db)):
    db_item = db.query(DBToDoList).filter(DBToDoList.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(db_item)
    db.commit()
    return {"detail": "Item deleted successfully"}

# === Добавим стартовые данные (один раз) ===
@app.on_event("startup")
async def startup():
    db = SessionLocal()
    if db.query(DBToDoList).count() == 0:
        items =  [
        DBToDoList(id=1, task="Отправить отчет Шефу", description="Х-отчет в конце дня. Не забыть!", completed=bool,)
        DBToDoList(id=2, task="Поставить сигнализацию в конце смены", description="Проверить горит-ли сигнал охраны", completed=bool),
        DBToDoList(id=3, task="Поставить буильник на час раньше", description="Утром нужно будет забрать дочку с рисования", completed=bool),
    ]
        db.add_all(items)
        db.commit()
    db.close()