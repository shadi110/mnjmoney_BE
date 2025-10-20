from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import psycopg
from psycopg.rows import dict_row
import os
from contextlib import asynccontextmanager
import time
from datetime import datetime
import bcrypt


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
                sslmode='require'
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


# Create tables
def create_tables():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Contact us table
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

        # Financial requests table with all survey fields
        cur.execute('''
                    CREATE TABLE IF NOT EXISTS financial_requests
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        -- Step 1: Employment Status
                        employment_status
                        VARCHAR
                    (
                        20
                    ) NOT NULL,

                        -- Step 2: Employment Type
                        employment_type VARCHAR
                    (
                        50
                    ) NOT NULL,

                        -- Step 3: Documents & History
                        has_pay_slips VARCHAR
                    (
                        20
                    ) NOT NULL,
                        previous_funds_history VARCHAR
                    (
                        20
                    ) NOT NULL,

                        -- Step 4: Services & Contact
                        service_interest VARCHAR
                    (
                        50
                    ) NOT NULL,
                        preferred_language VARCHAR
                    (
                        20
                    ) NOT NULL,

                        -- Contact Information
                        full_name VARCHAR
                    (
                        100
                    ) NOT NULL,
                        phone_number VARCHAR
                    (
                        50
                    ) NOT NULL,
                        email_address VARCHAR
                    (
                        100
                    ) NOT NULL,

                        -- Metadata
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
        # Admin Users table
        cur.execute('''
                    CREATE TABLE IF NOT EXISTS admin_users
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        username
                        VARCHAR
                    (
                        50
                    ) UNIQUE NOT NULL,
                        email VARCHAR
                    (
                        100
                    ) UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        full_name VARCHAR
                    (
                        100
                    ) NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')

        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database tables are ready")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")


# Pydantic models
class ContactForm(BaseModel):
    name: str
    email: str
    message: str


class FinancialRequestForm(BaseModel):
    # Step 1: Employment Status
    employment_status: str

    # Step 2: Employment Type
    employment_type: str

    # Step 3: Documents & History
    has_pay_slips: str
    previous_funds_history: str

    # Step 4: Services & Contact
    service_interest: str
    preferred_language: str

    # Contact Information
    full_name: str
    phone_number: str
    email_address: str
class AdminUserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str

class AdminUserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None

class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool
    created_at: str
    updated_at: str

class AdminUsersListResponse(BaseModel):
    success: bool
    total: int
    admin_users: List[AdminUserResponse]

class ContactResponse(BaseModel):
    id: int
    name: str
    email: str
    message: str
    created_at: str


class FinancialRequestResponse(BaseModel):
    id: int
    employment_status: str
    employment_type: str
    has_pay_slips: str
    previous_funds_history: str
    service_interest: str
    preferred_language: str
    full_name: str
    phone_number: str
    email_address: str
    created_at: str
    updated_at: str


class ContactsListResponse(BaseModel):
    success: bool
    total: int
    contacts: List[ContactResponse]


class FinancialRequestsListResponse(BaseModel):
    success: bool
    total: int
    financial_requests: List[FinancialRequestResponse]


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting FastAPI application...")
    create_tables()
    yield
    print("👋 Shutting down FastAPI application...")


app = FastAPI(
    title="MNJ Money API",
    description="Backend API for MNJ Money financial services",
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
    return {"message": "MNJ Money API is running"}


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


# Contact Us APIs
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

@app.delete("/api/contacts/{contact_id}")
async def delete_contact(contact_id: int):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "DELETE FROM contact_us WHERE id = %s RETURNING id",
            (contact_id,)
        )

        deleted_contact = cur.fetchone()
        conn.commit()

        cur.close()
        conn.close()

        if not deleted_contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        return {
            "success": True,
            "message": "Contact deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting contact: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error deleting contact"
        )
        
# Financial Requests APIs
@app.post("/api/financial-requests")
async def submit_financial_request(form: FinancialRequestForm):
    # Validate required fields
    required_fields = [
        form.employment_status, form.employment_type, form.has_pay_slips,
        form.previous_funds_history, form.service_interest, form.preferred_language,
        form.full_name, form.phone_number, form.email_address
    ]

    if not all(field.strip() for field in required_fields):
        raise HTTPException(status_code=400, detail="All fields are required")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO financial_requests (employment_status, employment_type, has_pay_slips, previous_funds_history,
                                            service_interest, preferred_language, full_name, phone_number,
                                            email_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, created_at, updated_at
            """,
            (
                form.employment_status.strip(), form.employment_type.strip(),
                form.has_pay_slips.strip(), form.previous_funds_history.strip(),
                form.service_interest.strip(), form.preferred_language.strip(),
                form.full_name.strip(), form.phone_number.strip(), form.email_address.strip()
            )
        )

        result = cur.fetchone()
        request_id, created_at, updated_at = result
        conn.commit()

        cur.close()
        conn.close()

        return {
            "success": True,
            "message": "Thank you for your financial request! We will contact you within 4 working hours.",
            "id": request_id,
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat()
        }

    except Exception as e:
        print(f"❌ Database error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error saving your financial request. Please try again."
        )


@app.get("/api/financial-requests", response_model=FinancialRequestsListResponse)
async def get_financial_requests(
        limit: Optional[int] = Query(100, ge=1, le=1000),
        offset: Optional[int] = Query(0, ge=0),
        search: Optional[str] = Query(None),
        service_type: Optional[str] = Query(None)
):
    try:
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict_row)

        query = """
                SELECT id, \
                       employment_status, \
                       employment_type, \
                       has_pay_slips,
                       previous_funds_history, \
                       service_interest, \
                       preferred_language,
                       full_name, \
                       phone_number, \
                       email_address, \
                       created_at, \
                       updated_at
                FROM financial_requests \
                """
        count_query = "SELECT COUNT(*) FROM financial_requests"
        params = []

        where_conditions = []

        if search:
            search_term = f"%{search}%"
            where_conditions.append("(full_name ILIKE %s OR email_address ILIKE %s OR phone_number ILIKE %s)")
            params.extend([search_term, search_term, search_term])

        if service_type:
            where_conditions.append("service_interest = %s")
            params.append(service_type)

        if where_conditions:
            where_clause = " WHERE " + " AND ".join(where_conditions)
            query += where_clause
            count_query += where_clause

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cur.execute(query, params)
        financial_requests = cur.fetchall()

        cur.execute(count_query, params[:len(params) - 2] if where_conditions else [])
        total = cur.fetchone()["count"]

        cur.close()
        conn.close()

        # Convert datetime objects to ISO format strings
        for request in financial_requests:
            request["created_at"] = request["created_at"].isoformat()
            request["updated_at"] = request["updated_at"].isoformat()

        return {
            "success": True,
            "total": total,
            "financial_requests": financial_requests
        }

    except Exception as e:
        print(f"❌ Error fetching financial requests: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error fetching financial requests list"
        )


@app.get("/api/financial-requests/{request_id}", response_model=FinancialRequestResponse)
async def get_financial_request(request_id: int):
    try:
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict_row)

        cur.execute(
            """
            SELECT id,
                   employment_status,
                   employment_type,
                   has_pay_slips,
                   previous_funds_history,
                   service_interest,
                   preferred_language,
                   full_name,
                   phone_number,
                   email_address,
                   created_at,
                   updated_at
            FROM financial_requests
            WHERE id = %s
            """,
            (request_id,)
        )

        financial_request = cur.fetchone()

        cur.close()
        conn.close()

        if not financial_request:
            raise HTTPException(status_code=404, detail="Financial request not found")

        financial_request["created_at"] = financial_request["created_at"].isoformat()
        financial_request["updated_at"] = financial_request["updated_at"].isoformat()
        return financial_request

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching financial request: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error fetching financial request"
        )


@app.delete("/api/financial-requests/{request_id}")
async def delete_financial_request(request_id: int):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "DELETE FROM financial_requests WHERE id = %s RETURNING id",
            (request_id,)
        )

        deleted_request = cur.fetchone()
        conn.commit()

        cur.close()
        conn.close()

        if not deleted_request:
            raise HTTPException(status_code=404, detail="Financial request not found")

        return {
            "success": True,
            "message": "Financial request deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting financial request: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error deleting financial request"
        )


# Password hashing utilities
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# Admin Users APIs
@app.post("/api/admin-users", response_model=AdminUserResponse)
async def create_admin_user(user: AdminUserCreate):
    if not all([user.username.strip(), user.email.strip(), user.password.strip(), user.full_name.strip()]):
        raise HTTPException(status_code=400, detail="All fields are required")
    
    if len(user.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

    try:
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict_row)

        # Check if username or email already exists
        cur.execute(
            "SELECT id FROM admin_users WHERE username = %s OR email = %s",
            (user.username.strip(), user.email.strip())
        )
        existing_user = cur.fetchone()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username or email already exists")

        # Hash password and create user
        password_hash = hash_password(user.password)
        
        cur.execute(
            """
            INSERT INTO admin_users (username, email, password_hash, full_name)
            VALUES (%s, %s, %s, %s)
            RETURNING id, username, email, full_name, is_active, created_at, updated_at
            """,
            (user.username.strip(), user.email.strip(), password_hash, user.full_name.strip())
        )

        new_user = cur.fetchone()
        conn.commit()

        cur.close()
        conn.close()

        # Convert datetime objects to ISO format strings
        new_user["created_at"] = new_user["created_at"].isoformat()
        new_user["updated_at"] = new_user["updated_at"].isoformat()

        return new_user

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error creating admin user"
        )

@app.get("/api/admin-users", response_model=AdminUsersListResponse)
async def get_admin_users(
    limit: Optional[int] = Query(100, ge=1, le=1000),
    offset: Optional[int] = Query(0, ge=0),
    search: Optional[str] = Query(None),
    active_only: Optional[bool] = Query(True)
):
    try:
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict_row)

        query = """
                SELECT id, username, email, full_name, is_active, created_at, updated_at
                FROM admin_users
                """
        count_query = "SELECT COUNT(*) FROM admin_users"
        params = []

        where_conditions = []

        if active_only:
            where_conditions.append("is_active = TRUE")

        if search:
            search_term = f"%{search}%"
            where_conditions.append("(username ILIKE %s OR email ILIKE %s OR full_name ILIKE %s)")
            params.extend([search_term, search_term, search_term])

        if where_conditions:
            where_clause = " WHERE " + " AND ".join(where_conditions)
            query += where_clause
            count_query += where_clause

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cur.execute(query, params)
        admin_users = cur.fetchall()

        cur.execute(count_query, params[:len(params) - 2] if where_conditions else [])
        total = cur.fetchone()["count"]

        cur.close()
        conn.close()

        # Convert datetime objects to ISO format strings
        for user in admin_users:
            user["created_at"] = user["created_at"].isoformat()
            user["updated_at"] = user["updated_at"].isoformat()

        return {
            "success": True,
            "total": total,
            "admin_users": admin_users
        }

    except Exception as e:
        print(f"❌ Error fetching admin users: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error fetching admin users list"
        )

@app.get("/api/admin-users/{user_id}", response_model=AdminUserResponse)
async def get_admin_user(user_id: int):
    try:
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict_row)

        cur.execute(
            """
            SELECT id, username, email, full_name, is_active, created_at, updated_at
            FROM admin_users
            WHERE id = %s
            """,
            (user_id,)
        )

        admin_user = cur.fetchone()

        cur.close()
        conn.close()

        if not admin_user:
            raise HTTPException(status_code=404, detail="Admin user not found")

        admin_user["created_at"] = admin_user["created_at"].isoformat()
        admin_user["updated_at"] = admin_user["updated_at"].isoformat()
        return admin_user

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching admin user: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error fetching admin user"
        )

# Statistics endpoint
@app.get("/api/statistics")
async def get_statistics():
    try:
        conn = get_db_connection()
        cur = conn.cursor(row_factory=dict_row)

        # Get contact counts
        cur.execute("SELECT COUNT(*) as contact_count FROM contact_us")
        contact_count = cur.fetchone()["contact_count"]

        # Get financial request counts
        cur.execute("SELECT COUNT(*) as financial_count FROM financial_requests")
        financial_count = cur.fetchone()["financial_count"]

        # Get service type breakdown
        cur.execute("""
                    SELECT service_interest, COUNT(*) as count
                    FROM financial_requests
                    GROUP BY service_interest
                    ORDER BY count DESC
                    """)
        service_breakdown = cur.fetchall()

        cur.close()
        conn.close()

        return {
            "success": True,
            "statistics": {
                "contact_requests": contact_count,
                "financial_requests": financial_count,
                "service_breakdown": service_breakdown,
                "total_requests": contact_count + financial_count
            }
        }

    except Exception as e:
        print(f"❌ Error fetching statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error fetching statistics"
        )
