from threading import Lock
from typing import Optional, Any

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="Desent API Quest",
    version="1.0.0",
)

# In-memory storage
books: dict[int, dict[str, Any]] = {}
next_book_id = 1
lock = Lock()

API_TOKEN = "desent-quest-token"


# Request models
class BookCreate(BaseModel):
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    year: int


class TokenRequest(BaseModel):
    username: str
    password: str


# Return 400 for invalid request bodies
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
def book_payload(book: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": book["id"],
        "title": book["title"],
        "author": book["author"],
        "year": book["year"],
    }


def validate_book(data: BookCreate) -> Optional[str]:
    if not data.title.strip():
        return "title is required"

    if not data.author.strip():
        return "author is required"

    return None


def is_authorized(authorization: Optional[str]) -> bool:
    return authorization == f"Bearer {API_TOKEN}"


# Level 1: Ping
@app.get("/ping")
def ping():
    return {"success": True}


# Level 2: Echo arbitrary JSON
@app.post("/echo")
async def echo(request: Request):
    return await request.json()


# Level 3: Create a book
@app.post("/books", status_code=201)
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
            "year": data.year,
        }
        books[next_book_id] = book
        next_book_id += 1

        return book_payload(book)


# Levels 3, 5 and 6: List, protect, search and paginate
@app.get("/books")
def list_books(
    author: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    authorization: Optional[str] = Header(default=None),
):
    if not is_authorized(authorization):
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

    if author is not None:
        results = [
            book for book in results
            if book["author"].casefold() == author.casefold()
        ]

    start = (page - 1) * limit
    selected = results[start:start + limit]

    # The challenge requires an array, not a pagination wrapper object.
    return [book_payload(book) for book in selected]


# Read one book
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


# Level 4: Update a book
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
        book["year"] = data.year

        return book_payload(book)


# Level 4: Delete a book
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


# Level 5: Issue an authentication token
@app.post("/auth/token")
def get_token(data: TokenRequest):
    if not data.username.strip() or not data.password.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid credentials"},
        )

    return {
        "access_token": API_TOKEN,
        "token_type": "bearer",
    }
