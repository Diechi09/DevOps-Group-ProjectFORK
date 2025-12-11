# ShopSmart — Price Comparison App

A full-stack price comparison application that helps users find the best prices across supermarkets.

## Features

- **Shopping List Management**: Add items to your shopping list with autocomplete
- **Multi-Store Comparison**: Compare prices across multiple supermarkets
- **Best Price Finder**: Automatically identifies the cheapest store for your basket
- **Persistent State**: Shopping list persists across page navigation and browser sessions
- **User Authentication**: Sign up and login functionality
- **Responsive Design**: Works on desktop and mobile devices

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│    Backend      │────▶│   PostgreSQL    │
│  (React/Vite)   │     │   (FastAPI)     │     │   (Azure)       │
│  Nginx + Azure  │     │  Azure App Svc  │     │  Flexible Srv   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Tech Stack

### Frontend
- React 18 with Vite
- React Router for navigation
- CSS (custom styling)
- Nginx (production)

### Backend
- FastAPI (Python 3.11)
- SQLAlchemy ORM
- Alembic migrations
- PostgreSQL database

### DevOps
- GitHub Actions CI/CD
- Azure Container Registry (ACR)
- Azure App Service (containers)
- Docker containerization

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (or use SQLite for development)

### Backend Setup

```bash
cd api

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="sqlite:///./test.db"  # Or your PostgreSQL URL
export CORS_ORIGINS="http://localhost:5173"

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set API URL (optional - defaults to /api/v1)
export VITE_API_BASE="http://localhost:8000/api/v1"

# Start development server
npm run dev
```

Visit `http://localhost:5173` to use the app.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/supermarkets/` | List all supermarkets |
| GET | `/api/v1/products/?q=<query>` | Search products |
| POST | `/api/v1/compare/` | Compare prices across stores |

### Compare Request Example

```json
POST /api/v1/compare/
{
  "items": ["Leche entera", "Huevos"],
  "stores": ["Mercadona", "Carrefour", "Lidl"]
}
```

## Deployment

The application is deployed to Azure using GitHub Actions:

- **Staging**: Deploys on push to `teamC2` branch
- **Production**: Deploys on push to `main` branch
- **Protection**: Pull requests targeting `main` must pass backend tests and a frontend build before merge (green main policy).

### Deployed URLs

- Frontend Staging: `https://shopsmart-frontend-staging.azurewebsites.net`
- Frontend Production: `https://shopsmart-frontend-production.azurewebsites.net`
- Backend Staging: `https://shopsmart-backend-staging.azurewebsites.net`
- Backend Production: `https://shopsmart-backend-production.azurewebsites.net`

### CI/CD Pipeline

```
Push to teamC2/main
       │
       ▼
┌─────────────────┐
│  Run Tests      │
│  (pytest)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Build Docker   │
│  Image          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Push to ACR    │
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Deploy to      │
│  App Service    │
└─────────────────┘
```

### Application Insights configuration

- Store the Application Insights connection string in your secret store as `APPINSIGHTS_CONNECTION_STRING` (GitHub Secrets or Azure DevOps variable group). Use the provided value: `InstrumentationKey=e0b63799-fea2-4eaa-b16c-51796f166920;IngestionEndpoint=https://westeurope-5.in.applicationinsights.azure.com/;LiveEndpoint=https://westeurope.livediagnostics.monitor.azure.com/;ApplicationId=485c12ed-ecd0-4f39-966b-770f3f364413`.
- The backend workflow automatically sets the `APPLICATIONINSIGHTS_CONNECTION_STRING` app setting on staging and production App Services when this secret is present.

## Project Structure

```
.
├── api/                    # Backend (FastAPI)
│   ├── app/
│   │   ├── main.py        # Application entry point
│   │   ├── routes/        # API route handlers
│   │   ├── services/      # Business logic
│   │   ├── models.py      # SQLAlchemy models
│   │   └── schemas.py     # Pydantic schemas
│   ├── alembic/           # Database migrations
│   ├── tests/             # Backend tests
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/              # Frontend (React/Vite)
│   ├── src/
│   │   ├── pages/         # Page components
│   │   ├── context/       # React contexts
│   │   ├── api.js         # API client
│   │   └── App.jsx        # Main app component
│   ├── Dockerfile
│   └── package.json
│
├── .github/workflows/     # CI/CD pipelines
│   ├── backend.yml
│   └── frontend.yml
│
└── docs/                  # Documentation
    └── DEVOPS_GUIDE.md    # Detailed DevOps setup
```

## Testing

### Backend Tests

```bash
cd api
pytest tests/ -v --cov=app
```

### Frontend Tests

```bash
cd frontend
npm test
```

## Environment Variables

### Backend

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host/db` |
| `CORS_ORIGINS` | Allowed CORS origins | `https://frontend.com,http://localhost:5173` |

### Frontend

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_BASE` | Backend API URL | `https://api.shopsmart.com/api/v1` |

## Contributing

1. Create a feature branch from `teamC2`
2. Make your changes
3. Run tests locally
4. Create a pull request

## Documentation

- [DevOps Guide](docs/DEVOPS_GUIDE.md) - CI/CD and infrastructure setup
- [API Testing](api/docs/TESTING.md) - Backend testing guide
- [Architecture](api/docs/ARCHITECTURE.md) - System architecture details

## License

This project is part of a university DevOps course assignment.
