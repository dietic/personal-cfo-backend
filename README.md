# PersonalCFO Backend

## 🚀 Project Status

### ✅ Completed Features

- ✅ **Database Setup**: SQLite for development, PostgreSQL-ready with Alembic migrations
- ✅ **Authentication System**: JWT-based auth with user registration/login
- ✅ **Card Management**: CRUD operations for credit/debit cards
- ✅ **Transaction Management**: CRUD with AI categorization support
- ✅ **Budget Tracking**: Budget creation with spending alerts
- ✅ **AI Integration**: OpenAI service for transaction categorization
- ✅ **Statement Processing**: PDF/CSV upload and parsing
- ✅ **Analytics**: Spending analysis and trend tracking
- ✅ **API Documentation**: FastAPI auto-generated docs
- ✅ **Database Migrations**: Alembic setup with initial schema

### 🚧 In Progress / Pending

- 🚧 **Email Service**: Resend integration for notifications
- 🚧 **Background Tasks**: Celery + Redis for reminders
- 🚧 **Testing Suite**: Comprehensive pytest tests
- 🚧 **Docker Setup**: Containerization for deployment
- 🚧 **Production Config**: Environment-specific configurations

---

## 🔧 Tech Stack

- **Frontend**: Next.js + TailwindCSS
- **Backend**: Python (FastAPI)
- **Database**: PostgreSQL
- **Auth**: Email/Password with JWT
- **AI/ML**: OpenAI for NLP parsing + categorization
- **Email**: Gmail API or IMAP for statement parsing
- **Scheduling**: Celery + Redis for reminders, periodic tasks
- **Charts/Analytics**: API endpoints for client-side chart rendering

---

## 🧠 Core Concepts

PersonalCFO is a personal finance management platform with a strong focus on:

- **Bank Statement Ingestion**
- **AI-Powered Spending Analysis**
- **Budget Tracking & Alerts**
- **Reminders for Recurrent Bills**
- **Editable Transaction Categorization**

---

## 🧾 Features Breakdown

### 1. **Authentication**

- Email/password sign-up and login
- JWT-based token authentication
- Secure password hashing with `bcrypt`

### 2. **Card Management**

- Add multiple credit/debit cards
- Each card has:

  - `card_name`
  - `payment_due_date`
  - `network_provider` (e.g. VISA, Mastercard)
  - `bank_provider` (e.g. BCP, Interbank)
  - `card_type` (credit or debit)

- View card details by ID

### 3. **Statement Uploading**

- PDF or CSV upload endpoint
- Future: Email integration (Gmail API or IMAP polling on date match)
- Parse statements → Normalize transactions

### 4. **Transaction Management**

- Transactions linked to a card
- Auto-tag via AI
- Editable transaction data
- Categories stored as tags: `food`, `housing`, `transport`, etc.

### 5. **Recurring Services**

- Add recurring bills:

  - `name`, `amount`, `due_date`

- Send reminders X days before via email/push

### 6. **Budgets**

- User-defined category limits per month
- Alert when category spend > 90%, > 100%

### 7. **Spending Analysis (AI)**

- Detect overspending patterns
- Suggest reductions
- Detect duplicates or anomalies

### 8. **Analytics API**

- `/analytics/category` — spending per category
- `/analytics/trends` — historical trend line
- `/analytics/comparison` — year-over-year

---

## 🗃️ Database Schema (simplified)

### Users

```sql
id UUID PK
email TEXT UNIQUE
password_hash TEXT
created_at TIMESTAMP
```

### Cards

```sql
id UUID PK
user_id UUID FK
card_name TEXT
payment_due_date DATE
network_provider TEXT
bank_provider TEXT
card_type TEXT
created_at TIMESTAMP
```

### Transactions

```sql
id UUID PK
card_id UUID FK
merchant TEXT
amount NUMERIC
category TEXT
transaction_date DATE
tags TEXT[]
created_at TIMESTAMP
```

### RecurringServices

```sql
id UUID PK
user_id UUID FK
name TEXT
amount NUMERIC
due_date DATE
category TEXT
reminder_days INTEGER
```

### Budgets

```sql
id UUID PK
user_id UUID FK
category TEXT
limit NUMERIC
month DATE (first of month)
```

---

## 🧠 AI Categorization Flow

1. On statement upload → parse raw data (merchant, amount, date)
2. Call OpenAI API with prompt-based classification
3. Store with predicted category & confidence
4. User can manually adjust category

---

## ⏰ Scheduled Tasks

- Statement check via email → Every 24h
- Bill reminders → X days before due
- Monthly budget reset/notifications

---

## 🛡️ Security

- RLS-style policies at API level: only access your own data
- Token validation on every route
- Encrypted credentials for external services

---

## 📈 Future Features

- SMS alerts
- Multicurrency support
- Shared budgets (family accounts)
- Auto-investment suggestions based on cashflow

---

## 🧪 Testing Strategy

- Use `pytest` for Python backend
- Coverage for:

  - Authentication
  - Card CRUD
  - Statement ingestion
  - Budget overages

---

## 🚀 Deployment

- Next.js frontend on **Vercel**
- Python backend on **Render**/**Railway**
- PostgreSQL hosted on **Supabase** or **NeonDB**
- Celery + Redis on **Upstash** or **Fly.io**

---

## 🔧 Environment Variables

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost/personalcfo_db

# JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Resend (Email)
RESEND_API_KEY=your-resend-api-key

# Redis (for Celery)
REDIS_URL=redis://localhost:6379

# File Storage
UPLOAD_DIR=./uploads

# App Settings
DEBUG=True
CORS_ORIGINS=["http://localhost:3000"]
```

---

## 📡 API Endpoints

### Authentication

- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh token

### Cards

- `GET /cards` - List user's cards
- `POST /cards` - Create new card
- `GET /cards/{card_id}` - Get card by ID
- `PUT /cards/{card_id}` - Update card
- `DELETE /cards/{card_id}` - Delete card

### Transactions

- `GET /transactions` - List transactions (with filters)
- `POST /transactions` - Create transaction
- `GET /transactions/{transaction_id}` - Get transaction
- `PUT /transactions/{transaction_id}` - Update transaction
- `DELETE /transactions/{transaction_id}` - Delete transaction

### Statements

- `POST /statements/upload` - Upload PDF/CSV statement
- `GET /statements` - List uploaded statements
- `POST /statements/{statement_id}/process` - Process statement with AI analysis
- `GET /statements/{statement_id}/insights` - Get AI insights for processed statement

### Budgets

- `GET /budgets` - List user budgets
- `POST /budgets` - Create budget
- `PUT /budgets/{budget_id}` - Update budget
- `DELETE /budgets/{budget_id}` - Delete budget
- `GET /budgets/alerts` - Get budget alerts

### Recurring Services

- `GET /recurring-services` - List recurring services
- `POST /recurring-services` - Create recurring service
- `PUT /recurring-services/{service_id}` - Update service
- `DELETE /recurring-services/{service_id}` - Delete service

### Analytics

- `GET /analytics/category` - Spending per category
- `GET /analytics/trends` - Historical trends
- `GET /analytics/comparison` - Year-over-year comparison
- `GET /analytics/insights` - AI-powered insights

### AI Services

- `POST /ai/categorize` - Categorize transaction
- `POST /ai/analyze-spending` - Analyze spending patterns
- `POST /ai/detect-anomalies` - Detect spending anomalies

---

## 📦 Dependencies

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
python-dotenv==1.0.0
openai==1.3.0
resend==0.6.0
celery==5.3.4
redis==5.0.1
pandas==2.1.3
PyPDF2==3.0.1
pydantic==2.5.0
pytest==7.4.3
pytest-asyncio==0.21.1
httpx==0.25.2
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Virtual environment (recommended)

### Setup

1. **Clone and setup virtual environment**:

   ```bash
   cd personal-cfo-backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run database migrations**:

   ```bash
   export DATABASE_URL="sqlite:///./personalcfo.db"
   alembic upgrade head
   ```

5. **Start the development server**:

   ```bash
   ./start_dev.sh
   # Or manually: uvicorn main:app --reload
   ```

6. **Access the API**:
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

### Testing

```bash
# Run the API test suite
python test_api.py

# Test individual endpoints
curl http://localhost:8000/health
```

---
