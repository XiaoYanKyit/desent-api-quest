
from threading import Lock
from typing import Optional

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="Desent API Quest",
    version="1.0.0",
)

# In-memory storage
books = {}
next_book_id = 1
lock = Lock()

API_TOKEN = "desent-quest-token"


# Request body models
class EchoBody(BaseModel):
    message: str
    name: str


class BookCreate(BaseModel):
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)


class TokenRequest(BaseModel):
    username: str
    password: str


# Global validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request"},
    )


# Helpers
def book_payload(book):
    return {
        "id": book["id"],
        "title": book["title"],
        "author": book["author"],
    }


def validate_book(data):
    if not data.title.strip():
        return "title is required"

    if not data.author.strip():
        return "author is required"

    return None


# Level 1: Ping
@app.get("/ping")
def ping():
    return {"success": True}

# Level 2: Echo
@app.post("/echo")
async def echo(request: Request):
    return await request.json()


# Level 3: Create and read books
@app.post("/books")
def create_book(data: BookCreate):
    global next_book_id

    error = validate_book(data)
    if error:
        return JSONResponse(
            status_code=400,
            content={"error": error},
        )

    with lock:
        book = {
            "id": next_book_id,
            "title": data.title.strip(),
            "author": data.author.strip(),
        }
        books[next_book_id] = book
        next_book_id += 1

    return JSONResponse(
        status_code=201,
        content=book_payload(book),
    )


@app.get("/books")
def list_books(
    author: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    authorization: Optional[str] = Header(default=None),
):
    # Authentication guard
    if authorization != f"Bearer {API_TOKEN}":
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized"},
        )

    if page < 1 or limit < 1:
        return JSONResponse(
            status_code=400,
            content={"error": "page and limit must be positive"},
        )

    with lock:
        results = list(books.values())

    if author:
        results = [
            book
            for book in results
            if book["author"].lower() == author.lower()
        ]

    total = len(results)
    start = (page - 1) * limit
    selected = results[start:start + limit]

    return {
        "books": [book_payload(book) for book in selected],
        "page": page,
        "limit": limit,
        "total": total,
    }


@app.get("/books/{book_id}")
def get_book(book_id: int):
    with lock:
        book = books.get(book_id)

    if book is None:
        return JSONResponse(
            status_code=404,
            content={"error": "Book not found"},
        )

    return book_payload(book)


# Level 4: Update and delete
@app.put("/books/{book_id}")
def update_book(book_id: int, data: BookCreate):
    error = validate_book(data)
    if error:
        return JSONResponse(
            status_code=400,
            content={"error": error},
        )

    with lock:
        book = books.get(book_id)

        if book is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Book not found"},
            )

        book["title"] = data.title.strip()
        book["author"] = data.author.strip()

        result = book_payload(book)

    return result


@app.delete("/books/{book_id}")
def delete_book(book_id: int):
    with lock:
        if book_id not in books:
            return JSONResponse(
                status_code=404,
                content={"error": "Book not found"},
            )

        del books[book_id]

    return {"message": "Book deleted successfully"}


# Level 5: Token endpoint
@app.post("/auth/token")
def get_token(data: TokenRequest):
    if not data.username.strip() or not data.password:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid credentials"},
        )

    return {
        "access_token": API_TOKEN,
        "token_type": "bearer",
    }
