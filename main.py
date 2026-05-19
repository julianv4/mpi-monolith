import asyncio
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy import Integer, String, Float, select
from pydantic import BaseModel

# ─── Database setup ───────────────────────────────────────────────────────────

DATABASE_URL = "mysql+aiomysql://root:Root1234!@localhost/monolito"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,        # límite del pool — el cuello de botella del TP
    max_overflow=10,    # conexiones extra antes de QueuePool limit exceeded
)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# ─── Models ───────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass

class Producto(Base):
    __tablename__ = "productos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    precio: Mapped[float] = mapped_column(Float)
    stock: Mapped[int] = mapped_column(Integer)

class PedidoORM(Base):
    __tablename__ = "pedidos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    producto_id: Mapped[int] = mapped_column(Integer)
    total: Mapped[float] = mapped_column(Float)

# ─── Schemas ──────────────────────────────────────────────────────────────────

class CrearPedidoRequest(BaseModel):
    producto_id: int
    cantidad: int

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI()

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/products")
async def listar_productos(db: AsyncSession = Depends(get_db)):
    # Query simple. El problema no está acá.
    # El problema es que usa la MISMA DB que POST /orders.
    result = await db.execute(select(Producto))
    return result.scalars().all()

@app.get("/products/{id}")
async def obtener_producto(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Producto).where(Producto.id == id))
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    return producto

@app.post("/orders", status_code=201)
async def crear_pedido(req: CrearPedidoRequest, db: AsyncSession = Depends(get_db)):
    # PASO 1: Abre transacción → genera lock en la fila del producto
    result = await db.execute(
        select(Producto).where(Producto.id == req.producto_id)
    )
    producto = result.scalar_one_or_none()

    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    if producto.stock < req.cantidad:
        raise HTTPException(400, "Stock insuficiente")

    # PASO 2: Simula pago lento — lock de DB sigue activo durante estos 3s
    # FastAPI puede atender otros requests (event loop libre)
    # MySQL (InnoDB) NO puede dar la fila a otros (lock activo)
    await asyncio.sleep(3)

    # PASO 3: Actualiza stock → cierra transacción → libera lock
    producto.stock -= req.cantidad
    db.add(PedidoORM(producto_id=req.producto_id, total=producto.precio * req.cantidad))
    await db.commit()

    return {"mensaje": "Pedido creado", "producto": producto.nombre, "total": producto.precio * req.cantidad}

@app.get("/health")
async def health():
    # Sin DB → sin locks → siempre rápido
    return {"status": "ok"}