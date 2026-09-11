# Backend architecture

FastAPI is the HTTP boundary, Pydantic schemas validate request and response data, and SQLAlchemy models provide a PostgreSQL-ready persistence layer. The current application creates tables on startup for a small Stage 1 environment; a migration tool should be added before production deployment.

Run the service with `uvicorn app.main:app --reload` from `backend`. Configure `DATABASE_URL` and `CORS_ORIGINS` through environment variables. The service has no authentication implementation yet; authentication and authorization must be added before handling real child data.
