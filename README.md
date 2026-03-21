# CineReserve API

High-performance RESTful backend for managing cinema operations, built with Django and Django REST Framework.

## Features
- Movie and Session management
- Seat reservation with distributed locking (Redis)
- JWT Authentication

## Setup
1. Clone the repository.
2. Setup environment using `poetry install`.
3. Configure your `.env` following `.env.example`.
4. Run migrations and start the server with Docker Compose.
