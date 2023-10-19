from fastapi import APIRouter
import os

prefix = "/admin"
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

router = APIRouter(prefix=prefix, tags=["admin"])
