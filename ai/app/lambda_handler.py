"""Entry point for the `ai` Lambda behind API Gateway."""

from mangum import Mangum

from app.main import app

handler = Mangum(app)
