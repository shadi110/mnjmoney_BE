from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import psycopg
from psycopg.rows import dict_row
import os
from contextlib import asynccontextmanager
import time


# Database connection with retry logic
def get_db_connection():
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        raise Exception("DATABASE_URL environment variable is not set")

    print(f"Attempting to connect to database...")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = psycopg.connect(
                database_url,
                sslmode='require'  # Always use SSL in production
            )
            print("✅ Successfully connected to PostgreSQL database")
            return conn
        except Exception as e:
            print(f"❌ Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print("Retrying in 5 seconds...")
                time.sleep(5)
            else:
                raise e


# Create table
def create_table():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
                    CREATE TABLE IF NOT EXISTS contact_us
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        name
                        VARCHAR
                    (
                        100
                    ) NOT NULL,
                        email VARCHAR
                    (
                        100
                    ) NOT NULL,
                        message TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Contact us table is ready")
    except Exception as e:
        print(f"❌ Error creating table: {e}")


# Pydantic models
class ContactForm(BaseModel):
    name: str
    email: str
    message: str


class ContactResponse(BaseModel):
    id: int
    name: str
    email: str
    message: str
    created_at: str


class ContactsListResponse(BaseModel):
    success: bool
    total: int
    contacts: List[ContactResponse]


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting FastAPI application...")
    create_table()
    yield
    print("👋 Shutting down FastAPI application...")


app = FastAPI(
    title="Contact API",
    description="FastAPI backend for contact form",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Contact API is running"}


@app.get("/api/health")
async def health_check():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()

        return {
            "status": "healthy",
            "database": "connected",
            "message": "Server and database are running correctly"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(e)}"
        )


@app.post("/api/contact")
async def submit_contact(form: ContactForm):
    if not form.name.strip() or not form.email.strip() or not form.message.strip():
        raise HTTPException(status_code=400, detail="All fields are required")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO contact_us (name, email, message) VALUES (%s, %s, %s) RETURNING id, created_at",
            (form.name.strip(), form.email.strip(), form.message.strip())
        )

        result = cur.fetchone()
        contact_id, created_at = result
        conn.commit()

        cur.close()
        conn.close()

        return {
            "success": True,
            "message": "Thank you for your message! We will get back to you soon.",
            "id": contact_id,
            "created_at": created_at.isoformat()
        }

    except Exception as e:
        print(f"❌ Database error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error saving your message. Please try again."
        )


@app.get("/api/contacts", response_model=ContactsListResponse)
async def get_contacts(
        limit: Optional[int] = Query(100, ge=1, le=1000),
        offset: Optional[int] = Query(0, ge=0),
        search: Optional[str] = Query(None)
):
    try:
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict_row)

        query = """
                SELECT id, name, email, message, created_at
                FROM contact_us \
                """
        count_query = "SELECT COUNT(*) FROM contact_us"
        params = []

        if search:
            search_term = f"%{search}%"
            query += " WHERE name ILIKE %s OR email ILIKE %s OR message ILIKE %s"
            count_query += " WHERE name ILIKE %s OR email ILIKE %s OR message ILIKE %s"
            params = [search_term, search_term, search_term]

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cur.execute(query, params)
        contacts = cur.fetchall()

        cur.execute(count_query, params[:3] if search else [])
        total = cur.fetchone()["count"]

        cur.close()
        conn.close()

        # Convert datetime objects to ISO format strings
        for contact in contacts:
            contact["created_at"] = contact["created_at"].isoformat()

        return {
            "success": True,
            "total": total,
            "contacts": contacts
        }

    except Exception as e:
        print(f"❌ Error fetching contacts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error fetching contacts list"
        )


@app.get("/api/contacts/{contact_id}", response_model=ContactResponse)
async def get_contact(contact_id: int):
    try:
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict_row)

        cur.execute(
            "SELECT id, name, email, message, created_at FROM contact_us WHERE id = %s",
            (contact_id,)
        )

        contact = cur.fetchone()

        cur.close()
        conn.close()

        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        contact["created_at"] = contact["created_at"].isoformat()
        return contact

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching contact: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error fetching contact"
        )